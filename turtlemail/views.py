import datetime
from typing import TYPE_CHECKING, Any
from django.db.models import Q
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    UserPassesTestMixin,
)
from django.contrib.auth.views import LoginView as _LoginView
from django.core.mail import send_mail
from django.db import transaction
from django.forms import BaseModelForm
from django.http import HttpRequest
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    TemplateView,
    UpdateView,
    ListView,
)

from turtlemail import routing
from turtlemail.human_id import human_id
from turtlemail.models import DeliveryLog, Packet, RouteStep, User
from turtlemail.types import AuthedHttpRequest

from .forms import (
    AuthenticationForm,
    InviteUserForm,
    PacketForm,
    StayForm,
    UserCreationForm,
    RouteStepRequestForm,
    RouteStepRoutingForm,
)
from .models import Invite, Stay, Route


class DeliveriesView(LoginRequiredMixin, ListView):
    template_name = "turtlemail/deliveries.jinja"
    model = Packet

    if TYPE_CHECKING:
        request: AuthedHttpRequest

    def get_queryset(self):
        queryset = super().get_queryset()
        user_routed_packages = queryset.filter(
            all_routes__steps__stay__user=self.request.user
        )
        queryset = queryset.filter(
            Q(sender=self.request.user) | Q(recipient=self.request.user)
        ).distinct()
        queryset = queryset.union(user_routed_packages).order_by("created_at")

        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        requested_steps = RouteStep.objects.filter(
            status=RouteStep.SUGGESTED,
            stay__user=self.request.user,
            route__status=Route.CURRENT,
        ).all()
        context["request_forms"] = [
            RouteStepRequestForm(step) for step in requested_steps
        ]
        routing_steps = RouteStep.objects.filter(
            previous_step__status=RouteStep.ONGOING,
            stay__user=self.request.user,
            route__status=Route.CURRENT,
        )
        context["routing_forms"] = [
            RouteStepRoutingForm(
                step, initial={"choice": RouteStepRoutingForm.Choices.YES}
            )
            for step in routing_steps
        ]
        return context


class HtmxUpdateRouteStepRequestView(UserPassesTestMixin, TemplateView):
    template_name = "turtlemail/route_step_request_form.jinja"
    success_url = reverse_lazy("requests")

    if TYPE_CHECKING:
        request: AuthedHttpRequest

    def test_func(self) -> bool | None:
        step = RouteStep.objects.select_related(
            "stay", "previous_step", "next_step"
        ).get(id=self.kwargs.get("pk"))
        return step.stay.user == self.request.user

    def get(self, _request: AuthedHttpRequest, pk):
        step = RouteStep.objects.select_related(
            "stay", "previous_step", "next_step"
        ).get(id=pk)
        form = RouteStepRequestForm(step)
        context = {
            "form": form,
            "on_packet_detail_page": self.request.GET.get("on_packet_detail_page"),
            "from_rejected_request": self.request.GET.get("from_rejected_request"),
        }
        return self.render_to_response(context)

    def post(self, request: AuthedHttpRequest, pk):
        step = RouteStep.objects.select_related(
            "stay", "previous_step", "next_step"
        ).get(id=pk)
        form = RouteStepRequestForm(step, data=request.POST)
        if form.is_valid():
            form.save()
            old_route = step.route
            maybe_new_route = routing.check_and_recalculate_route(
                old_route, starting_date=datetime.date.today()
            )
            new_proposed_step = RouteStep.objects.filter(
                status=RouteStep.SUGGESTED,
                stay__user=self.request.user,
                route__status=Route.CURRENT,
                packet=step.packet,
            ).first()
            # The algorithm proposed a new route step for the same packet,
            # directly show that proposal to the user.
            if maybe_new_route != old_route and new_proposed_step is not None:
                path = reverse(
                    "update_route_step_request", args=(new_proposed_step.id,)
                )
                query = urlencode({"from_rejected_request": True})
                target_url = f"{path}?{query}"
                return redirect(to=target_url)

            response = render(request, "turtlemail/htmx_response.jinja")
            response["HX-Refresh"] = "true"
            return response
        else:
            return self.render_to_response({"form": form})


class HtmxUpdateRouteStepRoutingView(UserPassesTestMixin, TemplateView):
    template_name = "turtlemail/route_step_routing_form.jinja"
    success_url = reverse_lazy("requests")

    def test_func(self) -> bool | None:
        step = RouteStep.objects.select_related(
            "stay", "previous_step", "next_step"
        ).get(id=self.kwargs.get("pk"))
        return step.stay.user == self.request.user

    def get(self, _request, pk):
        step = RouteStep.objects.select_related(
            "stay", "previous_step", "next_step"
        ).get(id=pk)
        form = RouteStepRoutingForm(
            step, initial={"choice": RouteStepRoutingForm.Choices.YES}
        )
        context = {
            "form": form,
            "on_packet_detail_page": self.request.GET.get("on_packet_detail_page"),
            # "from_rejected_request": self.request.GET.get("from_rejected_request"),
        }
        return self.render_to_response(context)

    def post(self, request, pk):
        step = RouteStep.objects.select_related(
            "stay", "previous_step", "next_step"
        ).get(id=pk)
        form = RouteStepRoutingForm(
            step,
            initial={"choice": RouteStepRoutingForm.Choices.YES},
            data=request.POST,
        )
        if form.is_valid():
            form.save()

            response = render(request, "turtlemail/htmx_response.jinja")
            response["HX-Refresh"] = "true"
            return response
        else:
            return self.render_to_response({"form": form})


class StaysView(LoginRequiredMixin, TemplateView):
    template_name = "turtlemail/stays.jinja"

    if TYPE_CHECKING:
        request: AuthedHttpRequest

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["stays"] = Stay.objects.filter(user=self.request.user, deleted=False)
        return context


class HtmxCreateStayView(LoginRequiredMixin, CreateView):
    model = Stay
    template_name = "turtlemail/_stays_create_form.jinja"
    prefix = "create_stay"
    success_url = reverse_lazy("stays")

    if TYPE_CHECKING:
        request: AuthedHttpRequest

    def get_form(self) -> BaseModelForm:
        return StayForm(self.request.user, **self.get_form_kwargs())

    def form_valid(self, form):
        form.instance.user = self.request.user
        stay = form.save()
        return render(
            self.request, "turtlemail/_stays_create_form_success.jinja", {"stay": stay}
        )


class HtmxStayDetailView(UserPassesTestMixin, DetailView):
    model = Stay
    template_name = "turtlemail/_stay_detail.jinja"

    if TYPE_CHECKING:
        request: AuthedHttpRequest

    def test_func(self):
        stay: Stay = self.get_object()  # type: ignore
        return stay.user == self.request.user


class HtmxUpdateStayView(LoginRequiredMixin, UpdateView):
    model = Stay
    template_name = "turtlemail/_stays_update_form.jinja"
    success_url = reverse_lazy("stays")

    if TYPE_CHECKING:
        request: AuthedHttpRequest

    def get_form(self) -> BaseModelForm:
        return StayForm(self.request.user, **self.get_form_kwargs())

    def get_prefix(self):
        return f"edit_stay_{self.get_object().id}"

    def form_valid(self, form):
        with transaction.atomic():
            form.instance.user = self.request.user
            stay: Stay = form.save()
            routes_to_recalculate = stay.cancel_dependent_route_steps()
            for route in routes_to_recalculate:
                routing.check_and_recalculate_route(route, datetime.date.today())

            return render(
                self.request,
                "turtlemail/_stay_detail.jinja",
                {"stay": stay, "include_messages": True},
            )


class HtmxDeleteStayView(LoginRequiredMixin, DeleteView):
    model = Stay
    success_url = reverse_lazy("stays")

    if TYPE_CHECKING:
        request: AuthedHttpRequest

    def delete(self, request: AuthedHttpRequest, *args, **kwargs):
        """
        Call the delete() method on the fetched object and then refresh + display message
        """

        with transaction.atomic():
            stay: Stay = self.get_object()  # type: ignore
            if stay.accepted_dependent_route_steps().exists():
                messages.add_message(
                    request,
                    messages.ERROR,
                    _(
                        "There is a delivery relying on this stay. It can't be deleted at the moment."
                    ),
                )
                return render(
                    request,
                    "turtlemail/_stay_detail.jinja",
                    {"stay": stay, "include_messages": True},
                )

            stay.mark_deleted()
            routes_to_recalculate = stay.cancel_dependent_route_steps()
            for route in routes_to_recalculate:
                routing.check_and_recalculate_route(route, datetime.date.today())

            messages.add_message(request, messages.INFO, _("Stay deleted."))
            return render(request, "turtlemail/htmx_response.jinja")


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "turtlemail/profile.jinja"


class SignUpView(CreateView):
    form_class = UserCreationForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup_and_login.jinja"

    def get_initial(self) -> dict[str, Any]:
        initial = super().get_initial()
        initial["email"] = self.request.GET.get("email") or None
        return initial


class LoginView(_LoginView):
    authentication_form = AuthenticationForm
    template_name = "registration/signup_and_login.jinja"


class CreatePacketView(LoginRequiredMixin, TemplateView):
    template_name = "turtlemail/create_packet_form.jinja"

    if TYPE_CHECKING:
        request: AuthedHttpRequest

    def get(self, _request: AuthedHttpRequest, *args, **kwargs):
        form = PacketForm()
        context = self.get_context_data(**kwargs)
        context["form"] = form
        return self.render_to_response(context)

    def post(self, request: AuthedHttpRequest, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        form = PacketForm(request.POST)
        context["form"] = form
        if not form.is_valid():
            return self.render_to_response(context)

        recipient_username = form.cleaned_data.get("recipient_username")
        if recipient_username is not None and len(recipient_username) > 0:
            context["search_results"] = User.objects.search_for_recipient(
                recipient_username, request.user.id
            )

        recipient_id = form.cleaned_data.get("recipient_id")
        if recipient_id is not None:
            context["recipient"] = User.objects.get(id=recipient_id)

        if not form.cleaned_data["confirm_recipient"]:
            return self.render_to_response(context)

        packet = Packet.objects.create(
            sender=request.user,
            recipient=context["recipient"],
            human_id=human_id.generate_id(),
        )

        DeliveryLog.objects.create(packet=packet, action=DeliveryLog.SEARCHING_ROUTE)

        routing.create_new_route(packet, starting_date=datetime.date.today())

        return redirect(to=reverse("packet_detail", args=(packet.human_id,)))


class PacketDetailView(UserPassesTestMixin, DetailView):
    template_name = "turtlemail/packet_detail.jinja"
    model = Packet
    slug_field = "human_id"

    if TYPE_CHECKING:
        request: AuthedHttpRequest

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        cx = super().get_context_data(**kwargs)
        packet: Packet = self.get_object()  # type: ignore
        cx["packet"] = packet
        current_route = packet.current_route()
        if current_route is not None:
            cx["users_route_steps"] = current_route.steps.filter(
                stay__user_id=self.request.user.id
            )
        else:
            cx["users_route_steps"] = []
        return cx

    def test_func(self) -> bool | None:
        """Only allow users involved with a packet to view it:

        a) Sender and Recipient
        b) People that will carry out a route step
        c) Superusers
        """
        packet: Packet = self.get_object()  # type: ignore
        is_part_of_route = RouteStep.objects.filter(
            packet_id=packet.id, stay__user__id=self.request.user.id
        ).exists()

        return (
            packet.is_sender_or_recipient(self.request.user)
            or is_part_of_route
            or self.request.user.is_superuser
        )


class HtmxInviteUserView(LoginRequiredMixin, CreateView):
    model = Invite
    template_name = "turtlemail/invite_user.jinja"
    form_class = InviteUserForm
    success_url = reverse_lazy("deliveries")

    if TYPE_CHECKING:
        request: AuthedHttpRequest

    def get_initial(self) -> dict[str, Any]:
        initial = super().get_initial()
        initial["email"] = self.request.GET.get("email", "")
        return initial

    def form_valid(self, form):
        with transaction.atomic():
            form.instance.invited_by = self.request.user
            invite = form.save()
            mail_text = render_to_string(
                "turtlemail/emails/invitation.jinja",
                {
                    "invited_by": self.request.user,
                    "invite_url": self.request.build_absolute_uri(
                        reverse("accept_invite", args=[invite.token])
                    ),
                },
            )
            send_mail(
                subject=_("You've been invited to turtlemail!"),
                message=mail_text,
                from_email=None,
                recipient_list=[form.cleaned_data["email"]],
            )
            messages.add_message(self.request, messages.SUCCESS, _("Invite sent!"))
            return super().form_valid(form)


class AcceptInviteView(View):
    def get(self, _request: HttpRequest, token: str):
        invite = Invite.objects.get(token=token)
        url = reverse("signup")
        query_params = urlencode({"email": invite.email})
        return redirect(f"{url}?{query_params}")
