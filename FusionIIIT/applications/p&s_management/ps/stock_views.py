from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from ps.selectors import get_store_item_stock_check_status


class StockCheckView(APIView):
    def get(self, request, item_id: int):
        required = request.query_params.get("required")
        if required is None:
            raise ValidationError({"required": "Query param required is required."})
        try:
            required_int = int(required)
        except ValueError as e:
            raise ValidationError({"required": "Must be an integer."}) from e
        if required_int < 0:
            raise ValidationError({"required": "Must be >= 0."})
        return Response(get_store_item_stock_check_status(item_id=item_id, required=required_int))

