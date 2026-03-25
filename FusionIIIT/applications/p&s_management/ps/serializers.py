from __future__ import annotations

from rest_framework import serializers

from ps.models import Indent, IndentItem, StockEntry, StockEntryItem, StoreItem


class StoreItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreItem
        fields = ["id", "name", "unit"]


class IndentItemWriteSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    estimated_cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )


class IndentItemReadSerializer(serializers.ModelSerializer):
    item = StoreItemSerializer()

    class Meta:
        model = IndentItem
        fields = ["id", "item", "quantity", "estimated_cost"]


class IndentSerializer(serializers.ModelSerializer):
    items = IndentItemReadSerializer(many=True, read_only=True)

    class Meta:
        model = Indent
        fields = [
            "id",
            "purpose",
            "justification",
            "estimated_cost",
            "status",
            "stock_available",
            "procurement_type",
            "department",
            "current_approver",
            "created_at",
            "updated_at",
            "items",
        ]
        read_only_fields = [
            "status",
            "stock_available",
            "procurement_type",
            "department",
            "current_approver",
            "created_at",
            "updated_at",
        ]


class IndentCreateSerializer(serializers.Serializer):
    purpose = serializers.CharField(max_length=255)
    justification = serializers.CharField(allow_blank=True, required=False)
    estimated_cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    items = IndentItemWriteSerializer(many=True)

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("At least one item is required.")
        item_ids = [i["item_id"] for i in items]
        if len(item_ids) != len(set(item_ids)):
            raise serializers.ValidationError("Duplicate item entries are not allowed.")
        return items


class HODActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["APPROVE", "REJECT", "FORWARD"])
    notes = serializers.CharField(required=False, allow_blank=True)
    forward_to_department_code = serializers.CharField(required=False, allow_blank=True)


class StockEntryItemWriteSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class StockEntryCreateSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True)
    items = StockEntryItemWriteSerializer(many=True)

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("At least one item is required.")
        item_ids = [i["item_id"] for i in items]
        if len(item_ids) != len(set(item_ids)):
            raise serializers.ValidationError("Duplicate item entries are not allowed.")
        return items


class PSAdminActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["BIDDING", "PURCHASE", "STOCK_ENTRY"])
    notes = serializers.CharField(required=False, allow_blank=True)


class StockEntryItemSerializer(serializers.ModelSerializer):
    item = StoreItemSerializer()

    class Meta:
        model = StockEntryItem
        fields = ["id", "item", "quantity"]


class StockEntrySerializer(serializers.ModelSerializer):
    items = StockEntryItemSerializer(many=True, read_only=True)

    class Meta:
        model = StockEntry
        fields = ["id", "indent", "acting_role", "notes", "created_at", "items"]
