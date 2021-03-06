from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.db import transaction
from django.db.models import Min, Count
from django.db.models.fields import Field
from django.core import serializers
from django.contrib import messages
from django.http import HttpResponse, HttpResponseBadRequest, Http404
from django.utils.html import format_html
from django.contrib.auth.decorators import login_required

from django_fresh_models.library import FreshFilterLibrary as ff

from .context_processors import current_event
from .models import (
    Contact,
    Deal,
    TaskType,
    Task,
    BoothSpace,
    TaskComment,
    TaskLog,
    Event,
)
from .forms import (
    ContactForm,
    DealForm,
    TaskTypeForm,
    QuickTaskForm,
    QuickStartForm,
    TaskCommentForm,
    ImportTaskTypesForm,
    ExportTaskTypesForm,
)

import datetime
import json


def show_model_data(cls, instance, exclude=[]):
    fs = cls._meta.get_fields(include_hidden=False)
    ret = dict()

    for f in fs:
        if not isinstance(f, Field) or f.name == "id" or f.name in exclude:
            continue

        display_name = ""
        value = None
        display_value = ""
        if f.is_relation:
            if f.many_to_many or f.one_to_many:
                set = getattr(instance, f.name)
                for related in set.all():
                    display_value += ff.filter(related, "a")
                display_name = (
                    f.verbose_name
                    or f.related_model._meta.verbose_name_plural.capitalize()
                )
                value = set
            else:
                related = getattr(instance, f.name)
                if related:
                    display_value = ff.filter(related, "a")
                display_name = (
                    f.verbose_name or f.related_model._meta.verbose_name.capitalize()
                )
                value = related
        else:
            display_value = getattr(
                instance, "get_" + f.name + "_display", getattr(instance, f.name)
            )
            display_name = f.verbose_name
            value = getattr(instance, f.name)

        ret[f.name] = {
            "display_name": display_name,
            "value": value,
            "display_value": display_value,
        }

    return ret


@login_required
def quickstart(request):
    if request.method == "GET":
        form = QuickStartForm(request.GET)
        if form.is_valid():
            if form.cleaned_data["what"]:
                try:
                    obj = TaskType.objects.get(name=form.cleaned_data["what"])
                    return redirect(
                        reverse("prospector:tasktypes.show", args=(obj.pk,))
                    )
                except TaskType.DoesNotExist:
                    pass

                try:
                    obj = Deal.objects.get(booth_name=form.cleaned_data["what"])
                    return redirect(reverse("prospector:deals.show", args=(obj.pk,)))
                except Deal.DoesNotExist:
                    messages.error(
                        request,
                        format_html(
                            "Il n'y a ni type de tâche, ni deal nommé <i>{}</i>.",
                            form.cleaned_data["what"],
                        ),
                    )
                    return redirect(reverse("prospector:index"))

    return redirect(reverse("prospector:tasks.list"))


@login_required
def index(request):
    """Gives overview :
    * Budget
    * Open booth spaces
    * Tasks to do and their status and their deadline
    """

    free_booths = BoothSpace.objects.filter(dealboothspace__isnull=True)

    # Show todos : (next tasks to do OR late tasks OR soon to be late tasks) grouped by tasktype
    next_task_pks_to_do = []
    for deal in Deal.objects.filter(task__isnull=False).distinct():
        tasks = deal.task_set.exclude(todo_state="0_done")
        minimum_depth = None
        for task in tasks:
            if not minimum_depth or task.tasktype.depth < minimum_depth:
                minimum_depth = task.tasktype.depth

        for task in tasks:
            if task.tasktype.depth == minimum_depth:
                next_task_pks_to_do.append(task.pk)

    next_tasks_to_do = Task.objects.filter(pk__in=next_task_pks_to_do)
    late_tasks = Task.objects.exclude(todo_state="0_done").filter(
        deadline__lt=datetime.datetime.now()
    )
    deadline_soon_tasks = Task.objects.exclude(todo_state="0_done").filter(
        deadline__lt=datetime.datetime.now() + datetime.timedelta(days=7)
    )

    to_do = (
        next_tasks_to_do.union(late_tasks)
        .union(deadline_soon_tasks)
        .order_by("deadline")
    )

    quickstartform = QuickStartForm()

    event = current_event(request)["current_event"]

    return render(
        request,
        "prospector/index.html",
        {
            "free_booths": free_booths,
            "to_do": to_do,
            "quickstartform": quickstartform,
            **(event.budget_data if event else {}),
        },
    )


@login_required
def budget(request):
    event = current_event(request)["current_event"]

    return render(
        request, "prospector/budget.html", event.budget_data if event else {},
    )


@login_required
def plan(request):
    """Helps with modifiying booth spaces and such
    * Asks to confirm that the mutex has been taken
    * Get the plan's svg somehow (make a separate function for that, as it may change)
    * Load the pro layer, link the polygons to the BoothSpaces with a svg id fioupfioup
    * Allow to do the following with booths:
        * Move (intelligently move tables as well)
        * Rename (keep links intact !)
        * Add (propose to link to a deal)
        * Remove (with correct warning if it is linked)
        * Undo/Redo
    * Saves constantly to django
    * When user is done, push back plan (another separate function), and ask user to release mutex.
    """

    return render(request, "prospector/index.html")


def list_view(model_class, templates_folder, *, archive=False):
    @login_required
    def the_view(request):
        if archive:
            qs = model_class.objects.deleted_only().order_by("deleted")
            return render(
                request,
                "prospector/{}/archive.html".format(templates_folder),
                {"qs": qs},
            )

        qs = model_class.objects.all()
        return render(
            request, "prospector/{}/list.html".format(templates_folder), {"qs": qs}
        )

    return the_view


def delete_view(model_class, view_prefix):
    @login_required
    def the_view(request, pk):
        obj = get_object_or_404(model_class, pk=pk)

        if request.method == "POST":
            obj.delete()
            messages.success(request, "Archivage effectué.")
            return redirect(reverse("prospector:{}.list".format(view_prefix)))

        return HttpResponse()

    return the_view


def undelete_view(model_class, view_prefix):
    @login_required
    def the_view(request, pk):
        try:
            obj = model_class.objects.deleted_only().get(pk=pk)
        except Contact.DoesNotExist:
            return Http404()

        if request.method == "POST":
            obj.save()
            messages.success(request, "Restauration effectuée.")
            return redirect(
                reverse("prospector:{}.show".format(view_prefix), args=(pk,))
            )

        return HttpResponse()

    return the_view


@login_required
def contacts_edit(request, pk=None, create=False):
    if create:
        obj = Contact()
    else:
        obj = get_object_or_404(Contact, pk=pk)

    if request.method == "POST":
        form = ContactForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Modifications sauvegardées.")
            return redirect(
                reverse("prospector:contacts.show", args=(form.instance.pk,))
            )
    else:
        form = ContactForm(instance=obj)

    return render(
        request,
        "prospector/contacts/edit.html",
        {"obj": obj, "form": form, "create": create},
    )


@login_required
def contacts_show(request, pk):
    obj = get_object_or_404(Contact, pk=pk)
    # Get all deals related to this object
    qs = Deal.objects.filter(contact__pk=obj.pk).order_by("-event__date")
    return render(request, "prospector/contacts/show.html", {"obj": obj, "qs": qs})


@login_required
def deals_edit(request, pk=None, create=False):
    if create:
        contact = (
            get_object_or_404(Contact, pk=request.GET["from_contact"])
            if "from_contact" in request.GET
            else None
        )
        obj = Deal(contact=contact)
    else:
        obj = get_object_or_404(Deal, pk=pk)

    if request.method == "POST":
        form = DealForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Modifications sauvegardées.")
            return redirect(reverse("prospector:deals.show", args=(form.instance.pk,)))
    else:
        form = DealForm(instance=obj)

    return render(
        request,
        "prospector/deals/edit.html",
        {"obj": obj, "form": form, "create": create},
    )


@login_required
def deals_show(request, pk):
    obj = get_object_or_404(Deal, pk=pk)

    if request.method == "POST":
        taskform = QuickTaskForm(request.POST)
        if taskform.is_valid():
            tasktype, created = TaskType.objects.get_or_create(
                name=taskform.cleaned_data["name"]
            )
            Task.objects.create(
                todo_state=taskform.cleaned_data["state"],
                deadline=taskform.cleaned_data["deadline"],
                deal=obj,
                tasktype=tasktype,
            )
            messages.success(
                request,
                format_html(
                    "Il faut maintenant <i>{}</i> pour <i>{}</i>.",
                    tasktype.name.lower(),
                    obj.booth_name,
                ),
            )
            if created:
                messages.info(
                    request,
                    format_html(
                        'Le type de tâche <i>{}</i> a été créé car il n\'existait pas.<br><a href="{}">Voir ici</a>.',
                        tasktype.name,
                        reverse("prospector:tasktypes.show", args=(tasktype.pk,)),
                    ),
                )
    else:
        taskform = QuickTaskForm(initial={"state": "5_contact_waits_pro"})

    return render(
        request, "prospector/deals/show.html", {"obj": obj, "taskform": taskform}
    )


@login_required
def deals_explaintags(request, pk):
    obj = get_object_or_404(Deal, pk=pk)
    tasks = {
        "price": obj.any_tasks_with_tag("price"),
        "boothspace": obj.any_tasks_with_tag("boothspace"),
        "contract": obj.any_tasks_with_tag("contract"),
    }
    return render(
        request, "prospector/deals/explaintags.html", {"obj": obj, "tasks": tasks}
    )


@login_required
def deals_defaulttasks(request, pk):
    obj = get_object_or_404(Deal, pk=pk)
    if request.method == "POST":
        types = TaskType.objects.filter(default_task_type=True)
        for type in types:
            task = Task(deal=obj, tasktype=type, todo_state="5_contact_waits_pro")
            task.save()
        return redirect(reverse("prospector:deals.show", args=(pk,)))

    return HttpResponse()


@login_required
def tasktypes_list(request):
    qs = (
        TaskType.objects.annotate(Count("task__deal"))
        .annotate(Min("task__deadline"))
        .order_by("task__deadline__min")
    )
    return render(request, "prospector/tasktypes/list.html", {"qs": qs})


@login_required
def tasktypes_edit(request, pk=None, create=False):
    if create:
        obj = TaskType()
    else:
        obj = get_object_or_404(TaskType, pk=pk)

    if request.method == "POST":
        form = TaskTypeForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Modifications sauvegardées.")
            return redirect(
                reverse("prospector:tasktypes.show", args=(form.instance.pk,))
            )
    else:
        form = TaskTypeForm(instance=obj)

    return render(
        request,
        "prospector/tasktypes/edit.html",
        {"obj": obj, "form": form, "create": create},
    )


@login_required
def tasktypes_import(request):
    if request.method == "POST":
        form = ImportTaskTypesForm(request.POST)

        if form.is_valid():
            try:
                id_mapping = {}
                json_list = list(
                    serializers.deserialize("json", form.cleaned_data["json_list"])
                )
                retry_list = []
                number_of_iterations_since_last_resolution = 0

                # Renumber id's
                with transaction.atomic():
                    while len(json_list) + len(retry_list):
                        if len(json_list):
                            obj = json_list.pop(0)

                            id_in_json = obj.object.id
                            obj.object.id = None
                            obj.save()
                            id_mapping[id_in_json] = obj.object.id
                        elif len(retry_list):
                            obj = retry_list.pop(0)

                        prev_id = obj.object.typical_prev_task_id
                        if prev_id:
                            if prev_id in id_mapping:
                                obj.object.typical_prev_task_id = id_mapping[prev_id]
                                number_of_iterations_since_last_resolution = 0
                                obj.save()
                            else:
                                retry_list.append(obj)
                                number_of_iterations_since_last_resolution += 1

                        if number_of_iterations_since_last_resolution > len(json_list):
                            # We have made a full iteration of the list without resolving.
                            # This implies the submitted data refers to absent data, which is not supported.
                            raise ValueError(
                                "The submitted data contains references to absent data."
                            )

                messages.success(request, "Import effectué.")
                return redirect(reverse("prospector:tasktypes.list", args=[]))

            except Exception as e:
                messages.error(request, "Exception lors de l'import : {}".format(e))
    else:
        form = ImportTaskTypesForm()

    return render(request, "prospector/tasktypes/import.html", {"form": form})


@login_required
def tasktypes_export(request):
    if request.method == "POST":
        form = ExportTaskTypesForm(request.POST)

        if form.is_valid():
            try:
                result = serializers.serialize(
                    "json",
                    form.cleaned_data["which_tasktypes"],
                    fields=[
                        "default_task_type",
                        "description",
                        "name",
                        "tags",
                        "typical_prev_task",
                        "useful_views",
                        "wiki_page",
                    ],
                )
                result = json.dumps(json.loads(result), indent=4, sort_keys=True)

                messages.success(request, "Export effectué.")
            except Exception as e:
                messages.error(request, "Exception lors de l'export : {}".format(e))

    else:
        form = ExportTaskTypesForm()
        result = ""

    return render(
        request, "prospector/tasktypes/export.html", {"form": form, "result": result}
    )


@login_required
def tasks_list(request):
    return render(request, "prospector/tasks/list.html")


@login_required
def tasks_history(request, pk):
    obj = get_object_or_404(Task, pk=pk)
    return render(request, "prospector/tasks/history.html", {"obj": obj})


@login_required
def tasks_comments(request, pk):
    obj = get_object_or_404(Task, pk=pk)
    if request.method == "POST":
        form = TaskCommentForm(request.POST)
        if form.is_valid():
            TaskComment.objects.create(
                task=obj, author=request.user, text=form.cleaned_data["text"]
            )
    else:
        form = TaskCommentForm()
    return render(request, "prospector/tasks/comments.html", {"obj": obj, "form": form})


@login_required
def tasks_delete_comment(request, pk):
    obj = get_object_or_404(TaskComment, pk=pk)
    if request.method == "POST":
        obj.delete()

    return HttpResponse()


@login_required
def tasks_list_embed(request):
    qs = Task.objects.all()
    fixed_tasktype = False
    fixed_deal = False
    if "fixed_tasktype" in request.GET:
        fixed_tasktype = True
        qs = qs.filter(tasktype__pk=request.GET["fixed_tasktype"])
    if "fixed_deal" in request.GET:
        fixed_deal = True
        qs = qs.filter(deal__pk=request.GET["fixed_deal"])

    # Not crazy efficient. However, "depth" is a recursively-computed property, so doing it in the DB is not standard.
    # If you're motivated, see https://mariadb.com/kb/en/recursive-common-table-expressions-overview/
    qs = sorted(qs, key=lambda task: task.tasktype.depth)
    return render(
        request,
        "prospector/tasks/list_embed.html",
        {"qs": qs, "fixed_deal": fixed_deal, "fixed_tasktype": fixed_tasktype},
    )


@login_required
def tasks_set_todostate(request, pk):
    if request.method == "POST":
        if "state" not in request.GET:
            return HttpResponseBadRequest()
        with transaction.atomic():
            obj = Task.objects.select_for_update().get(pk=pk)
            if obj.todo_state != request.GET["state"]:
                obj.todo_state_logged = False
                obj.todo_state = request.GET["state"]
                obj.save()

    return HttpResponse()


@login_required
def tasks_log_todostate(request, pk):
    if request.method == "POST":
        with transaction.atomic():
            obj = Task.objects.select_for_update().get(pk=pk)
            if not obj.tasklog_set.exists():
                TaskLog.objects.create(
                    new_todo_state=obj.todo_state,
                    old_todo_state=None,
                    task=obj,
                    user=request.user,
                )
            else:
                log = obj.tasklog_set.latest()
                if log.new_todo_state != obj.todo_state:
                    TaskLog.objects.create(
                        new_todo_state=obj.todo_state,
                        old_todo_state=log.new_todo_state,
                        task=obj,
                        user=request.user,
                    )

            obj.todo_state_logged = True
            obj.save()

    return HttpResponse()


@login_required
def tasktypes_show(request, pk):
    obj = TaskType.objects.get(pk=pk)
    show_data = show_model_data(TaskType, obj)
    qs = Task.objects.filter(tasktype__pk=obj.pk)
    return render(
        request,
        "prospector/tasktypes/show.html",
        {"show_data": show_data, "obj": obj, "qs": qs},
    )


@login_required
def events_list(request):
    qs = Event.objects.order_by("-date")
    return render(request, "prospector/events/list.html", {"qs": qs})


@login_required
def events_show(request, pk):
    if request.method == "POST":
        if request.POST["what"] == "please_make_this_current":
            old_current = Event.objects.select_for_update().filter(current=True)
            new_current = Event.objects.select_for_update().filter(pk=pk)
            with transaction.atomic():
                old_current.update(current=False)
                new_current.update(current=True)
            messages.success(
                request,
                "L'événement {} est maintenant actuel !".format(new_current.get().name),
            )

    obj = Event.objects.get(pk=pk)
    show_data = show_model_data(Event, obj)
    return render(
        request, "prospector/events/show.html", {"show_data": show_data, "obj": obj}
    )


# TODO: Find a way to select the fanzines


# Create your views here.
