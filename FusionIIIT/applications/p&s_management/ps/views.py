from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from ps.rbac import ActingRole, get_actor_context
from ps.selectors import (
    get_indent_decisions_for_actor_data,
    get_indents_for_actor_data,
    get_me_payload,
    get_procurement_ready_indents_for_actor_data,
    get_ps_admin_indents_by_category,
    get_stock_breakdown_data,
)
from ps.services import (
    apply_hod_action,
    apply_ps_admin_action,
    check_stock_action,
    create_indent,
    create_stock_entry,
)
from ps.serializers import (
    HODActionSerializer,
    IndentCreateSerializer,
    PSAdminActionSerializer,
    StockEntryCreateSerializer,
)


class IndentViewSet(viewsets.ViewSet):
    def _actor(self):
        try:
            return get_actor_context(self.request)
        except PermissionError as e:
            raise PermissionDenied(str(e)) from e

    def list(self, request):
        actor = self._actor()
        return Response(get_indents_for_actor_data(actor))

    def create(self, request):
        actor = self._actor()
        serializer = IndentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = create_indent(serializer.validated_data, actor, request.user)
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="decisions")
    def decisions(self, request):
        actor = self._actor()
        if actor.role == ActingRole.EMPLOYEE:
            raise PermissionDenied("Only approver roles can view decisions.")
        return Response(get_indent_decisions_for_actor_data(actor, request.user))

    @action(detail=False, methods=["get"], url_path="procurement-ready")
    def procurement_ready(self, request):
        actor = self._actor()
        return Response(get_procurement_ready_indents_for_actor_data(actor))

    @action(detail=True, methods=["post"], url_path="hod-action")
    def hod_action(self, request, pk=None):
        actor = self._actor()
        data_ser = HODActionSerializer(data=request.data)
        data_ser.is_valid(raise_exception=True)

        action_name = data_ser.validated_data["action"]
        notes = data_ser.validated_data.get("notes", "")
        forward_to_department_code = data_ser.validated_data.get(
            "forward_to_department_code"
        )

        data = apply_hod_action(
            indent_id=pk,
            actor=actor,
            action_name=action_name,
            notes=notes,
            forward_to_department_code=forward_to_department_code,
            request_user=request.user,
        )
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="stock-breakdown")
    def stock_breakdown(self, request, pk=None):
        actor = self._actor()
        return Response(get_stock_breakdown_data(indent_id=pk, actor=actor))

    @action(detail=True, methods=["post"], url_path="check-stock")
    def check_stock_action(self, request, pk=None):
        actor = self._actor()
        return Response(
            check_stock_action(indent_id=pk, actor=actor, request_user=request.user)
        )

    @action(detail=True, methods=["post"], url_path="create-stock-entry")
    def create_stock_entry(self, request, pk=None):
        actor = self._actor()
        serializer = StockEntryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = create_stock_entry(
            indent_id=pk,
            actor=actor,
            request_user=request.user,
            item_lines=serializer.validated_data["items"],
            notes=serializer.validated_data.get("notes", ""),
        )
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="ps-admin-categories")
    def ps_admin_categories(self, request):
        actor = self._actor()
        return Response(get_ps_admin_indents_by_category(actor))

    @action(detail=True, methods=["post"], url_path="ps-admin-action")
    def ps_admin_action(self, request, pk=None):
        actor = self._actor()
        serializer = PSAdminActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action_name = serializer.validated_data["action"]
        notes = serializer.validated_data.get("notes", "")

        data = apply_ps_admin_action(
            indent_id=pk,
            actor=actor,
            action_name=action_name,
            notes=notes,
            request_user=request.user,
        )
        return Response(data, status=status.HTTP_200_OK)


class MeViewSet(viewsets.ViewSet):
    """
    Returns identity + allowed acting roles for the authenticated user.
    This endpoint does NOT require X-Acting-Role.
    """

    def list(self, request):
        return Response(get_me_payload(request.user))
