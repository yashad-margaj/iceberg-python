# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

from textwrap import dedent
from typing import Any, Dict, List

import pyarrow as pa
import pytest

from pyiceberg.exceptions import ResolveError, ValidationError
from pyiceberg.schema import (
    Accessor,
    Schema,
    build_position_accessors,
    index_by_id,
    index_by_name,
    promote,
    prune_columns,
    sanitize_column_names,
)
from pyiceberg.table.update.schema import UpdateSchema
from pyiceberg.typedef import EMPTY_DICT, StructProtocol
from pyiceberg.types import (
    BinaryType,
    BooleanType,
    DateType,
    DecimalType,
    DoubleType,
    FixedType,
    FloatType,
    IcebergType,
    IntegerType,
    ListType,
    LongType,
    MapType,
    NestedField,
    PrimitiveType,
    StringType,
    StructType,
    TimestampType,
    TimestamptzType,
    TimeType,
    UUIDType,
)

TEST_PRIMITIVE_TYPES = [
    BooleanType(),
    IntegerType(),
    LongType(),
    FloatType(),
    DoubleType(),
    DecimalType(10, 2),
    DecimalType(100, 2),
    StringType(),
    DateType(),
    TimeType(),
    TimestamptzType(),
    TimestampType(),
    BinaryType(),
    FixedType(16),
    FixedType(20),
    UUIDType(),
]


def test_schema_str(table_schema_simple: Schema) -> None:
    """Test casting a schema to a string"""
    assert str(table_schema_simple) == dedent(
        """\
    table {
      1: foo: optional string
      2: bar: required int
      3: baz: optional boolean
    }"""
    )


def test_schema_repr_single_field() -> None:
    """Test schema representation"""
    actual = repr(Schema(NestedField(field_id=1, name="foo", field_type=StringType()), schema_id=1))
    expected = "Schema(NestedField(field_id=1, name='foo', field_type=StringType(), required=False), schema_id=1, identifier_field_ids=[])"
    assert expected == actual


def test_schema_repr_two_fields() -> None:
    """Test schema representation"""
    actual = repr(
        Schema(
            NestedField(field_id=1, name="foo", field_type=StringType()),
            NestedField(field_id=2, name="bar", field_type=IntegerType(), required=False),
            schema_id=1,
        )
    )
    expected = "Schema(NestedField(field_id=1, name='foo', field_type=StringType(), required=False), NestedField(field_id=2, name='bar', field_type=IntegerType(), required=False), schema_id=1, identifier_field_ids=[])"
    assert expected == actual


def test_schema_raise_on_duplicate_names() -> None:
    """Test schema representation"""
    with pytest.raises(ValueError) as exc_info:
        Schema(
            NestedField(field_id=1, name="foo", field_type=StringType(), required=False),
            NestedField(field_id=2, name="bar", field_type=IntegerType(), required=True),
            NestedField(field_id=3, name="baz", field_type=BooleanType(), required=False),
            NestedField(field_id=4, name="baz", field_type=BooleanType(), required=False),
            schema_id=1,
            identifier_field_ids=[2],
        )

    assert "Invalid schema, multiple fields for name baz: 3 and 4" in str(exc_info.value)


def test_schema_index_by_id_visitor(table_schema_nested: Schema) -> None:
    """Test index_by_id visitor function"""
    index = index_by_id(table_schema_nested)
    assert index == {
        1: NestedField(field_id=1, name="foo", field_type=StringType(), required=False),
        2: NestedField(field_id=2, name="bar", field_type=IntegerType(), required=True),
        3: NestedField(field_id=3, name="baz", field_type=BooleanType(), required=False),
        4: NestedField(
            field_id=4,
            name="qux",
            field_type=ListType(element_id=5, element_type=StringType(), element_required=True),
            required=True,
        ),
        5: NestedField(field_id=5, name="element", field_type=StringType(), required=True),
        6: NestedField(
            field_id=6,
            name="quux",
            field_type=MapType(
                key_id=7,
                key_type=StringType(),
                value_id=8,
                value_type=MapType(key_id=9, key_type=StringType(), value_id=10, value_type=IntegerType(), value_required=True),
                value_required=True,
            ),
            required=True,
        ),
        7: NestedField(field_id=7, name="key", field_type=StringType(), required=True),
        9: NestedField(field_id=9, name="key", field_type=StringType(), required=True),
        8: NestedField(
            field_id=8,
            name="value",
            field_type=MapType(key_id=9, key_type=StringType(), value_id=10, value_type=IntegerType(), value_required=True),
            required=True,
        ),
        10: NestedField(field_id=10, name="value", field_type=IntegerType(), required=True),
        11: NestedField(
            field_id=11,
            name="location",
            field_type=ListType(
                element_id=12,
                element_type=StructType(
                    NestedField(field_id=13, name="latitude", field_type=FloatType(), required=False),
                    NestedField(field_id=14, name="longitude", field_type=FloatType(), required=False),
                ),
                element_required=True,
            ),
            required=True,
        ),
        12: NestedField(
            field_id=12,
            name="element",
            field_type=StructType(
                NestedField(field_id=13, name="latitude", field_type=FloatType(), required=False),
                NestedField(field_id=14, name="longitude", field_type=FloatType(), required=False),
            ),
            required=True,
        ),
        13: NestedField(field_id=13, name="latitude", field_type=FloatType(), required=False),
        14: NestedField(field_id=14, name="longitude", field_type=FloatType(), required=False),
        15: NestedField(
            field_id=15,
            name="person",
            field_type=StructType(
                NestedField(field_id=16, name="name", field_type=StringType(), required=False),
                NestedField(field_id=17, name="age", field_type=IntegerType(), required=True),
            ),
            required=False,
        ),
        16: NestedField(field_id=16, name="name", field_type=StringType(), required=False),
        17: NestedField(field_id=17, name="age", field_type=IntegerType(), required=True),
    }


def test_schema_index_by_name_visitor(table_schema_nested: Schema) -> None:
    """Test index_by_name visitor function"""
    table_schema_nested = Schema(
        NestedField(field_id=1, name="foo", field_type=StringType(), required=False),
        NestedField(field_id=2, name="bar", field_type=IntegerType(), required=True),
        NestedField(field_id=3, name="baz", field_type=BooleanType(), required=False),
        NestedField(
            field_id=4,
            name="qux",
            field_type=ListType(element_id=5, element_type=StringType(), element_required=True),
            required=True,
        ),
        NestedField(
            field_id=6,
            name="quux",
            field_type=MapType(
                key_id=7,
                key_type=StringType(),
                value_id=8,
                value_type=MapType(key_id=9, key_type=StringType(), value_id=10, value_type=IntegerType(), value_required=True),
                value_required=True,
            ),
            required=True,
        ),
        NestedField(
            field_id=11,
            name="location",
            field_type=ListType(
                element_id=12,
                element_type=StructType(
                    NestedField(field_id=13, name="latitude", field_type=FloatType(), required=False),
                    NestedField(field_id=14, name="longitude", field_type=FloatType(), required=False),
                ),
                element_required=True,
            ),
            required=True,
        ),
        NestedField(
            field_id=15,
            name="person",
            field_type=StructType(
                NestedField(field_id=16, name="name", field_type=StringType(), required=False),
                NestedField(field_id=17, name="age", field_type=IntegerType(), required=True),
            ),
            required=False,
        ),
        schema_id=1,
        identifier_field_ids=[2],
    )
    index = index_by_name(table_schema_nested)
    assert index == {
        "foo": 1,
        "bar": 2,
        "baz": 3,
        "qux": 4,
        "qux.element": 5,
        "quux": 6,
        "quux.key": 7,
        "quux.value": 8,
        "quux.value.key": 9,
        "quux.value.value": 10,
        "location": 11,
        "location.element": 12,
        "location.element.latitude": 13,
        "location.element.longitude": 14,
        "location.latitude": 13,
        "location.longitude": 14,
        "person": 15,
        "person.name": 16,
        "person.age": 17,
    }


def test_schema_find_column_name(table_schema_nested: Schema) -> None:
    """Test finding a column name using its field ID"""
    assert table_schema_nested.find_column_name(1) == "foo"
    assert table_schema_nested.find_column_name(2) == "bar"
    assert table_schema_nested.find_column_name(3) == "baz"
    assert table_schema_nested.find_column_name(4) == "qux"
    assert table_schema_nested.find_column_name(5) == "qux.element"
    assert table_schema_nested.find_column_name(6) == "quux"
    assert table_schema_nested.find_column_name(7) == "quux.key"
    assert table_schema_nested.find_column_name(8) == "quux.value"
    assert table_schema_nested.find_column_name(9) == "quux.value.key"
    assert table_schema_nested.find_column_name(10) == "quux.value.value"
    assert table_schema_nested.find_column_name(11) == "location"
    assert table_schema_nested.find_column_name(12) == "location.element"
    assert table_schema_nested.find_column_name(13) == "location.element.latitude"
    assert table_schema_nested.find_column_name(14) == "location.element.longitude"


def test_schema_find_column_name_on_id_not_found(table_schema_nested: Schema) -> None:
    """Test raising an error when a field ID cannot be found"""
    assert table_schema_nested.find_column_name(99) is None


def test_schema_find_column_name_by_id(table_schema_simple: Schema) -> None:
    """Test finding a column name given its field ID"""
    assert table_schema_simple.find_column_name(1) == "foo"
    assert table_schema_simple.find_column_name(2) == "bar"
    assert table_schema_simple.find_column_name(3) == "baz"


def test_schema_find_field_by_id(table_schema_simple: Schema) -> None:
    """Test finding a column using its field ID"""
    index = index_by_id(table_schema_simple)

    column1 = index[1]
    assert isinstance(column1, NestedField)
    assert column1.field_id == 1
    assert column1.field_type == StringType()
    assert column1.required is False

    column2 = index[2]
    assert isinstance(column2, NestedField)
    assert column2.field_id == 2
    assert column2.field_type == IntegerType()
    assert column2.required is True

    column3 = index[3]
    assert isinstance(column3, NestedField)
    assert column3.field_id == 3
    assert column3.field_type == BooleanType()
    assert column3.required is False


def test_schema_find_field_by_id_raise_on_unknown_field(table_schema_simple: Schema) -> None:
    """Test raising when the field ID is not found among columns"""
    index = index_by_id(table_schema_simple)
    with pytest.raises(Exception) as exc_info:
        _ = index[4]
    assert str(exc_info.value) == "4"


def test_schema_find_field_type_by_id(table_schema_simple: Schema) -> None:
    """Test retrieving a columns' type using its field ID"""
    index = index_by_id(table_schema_simple)
    assert index[1] == NestedField(field_id=1, name="foo", field_type=StringType(), required=False)
    assert index[2] == NestedField(field_id=2, name="bar", field_type=IntegerType(), required=True)
    assert index[3] == NestedField(field_id=3, name="baz", field_type=BooleanType(), required=False)


def test_index_by_id_schema_visitor_raise_on_unregistered_type() -> None:
    """Test raising a NotImplementedError when an invalid type is provided to the index_by_id function"""
    with pytest.raises(NotImplementedError) as exc_info:
        index_by_id("foo")  # type: ignore
    assert "Cannot visit non-type: foo" in str(exc_info.value)


def test_schema_find_field(table_schema_simple: Schema) -> None:
    """Test finding a field in a schema"""
    assert (
        table_schema_simple.find_field(1)
        == table_schema_simple.find_field("foo")
        == table_schema_simple.find_field("FOO", case_sensitive=False)
        == NestedField(field_id=1, name="foo", field_type=StringType(), required=False)
    )
    assert (
        table_schema_simple.find_field(2)
        == table_schema_simple.find_field("bar")
        == table_schema_simple.find_field("BAR", case_sensitive=False)
        == NestedField(field_id=2, name="bar", field_type=IntegerType(), required=True)
    )
    assert (
        table_schema_simple.find_field(3)
        == table_schema_simple.find_field("baz")
        == table_schema_simple.find_field("BAZ", case_sensitive=False)
        == NestedField(field_id=3, name="baz", field_type=BooleanType(), required=False)
    )


def test_schema_find_type(table_schema_simple: Schema) -> None:
    """Test finding the type of a column given its field ID"""
    assert (
        table_schema_simple.find_type(1)
        == table_schema_simple.find_type("foo")
        == table_schema_simple.find_type("FOO", case_sensitive=False)
        == StringType()
    )
    assert (
        table_schema_simple.find_type(2)
        == table_schema_simple.find_type("bar")
        == table_schema_simple.find_type("BAR", case_sensitive=False)
        == IntegerType()
    )
    assert (
        table_schema_simple.find_type(3)
        == table_schema_simple.find_type("baz")
        == table_schema_simple.find_type("BAZ", case_sensitive=False)
        == BooleanType()
    )


def test_build_position_accessors(table_schema_nested: Schema) -> None:
    accessors = build_position_accessors(table_schema_nested)
    assert accessors == {
        1: Accessor(position=0, inner=None),
        2: Accessor(position=1, inner=None),
        3: Accessor(position=2, inner=None),
        4: Accessor(position=3, inner=None),
        6: Accessor(position=4, inner=None),
        11: Accessor(position=5, inner=None),
        15: Accessor(position=6, inner=None),
        16: Accessor(position=6, inner=Accessor(position=0, inner=None)),
        17: Accessor(position=6, inner=Accessor(position=1, inner=None)),
    }


def test_build_position_accessors_with_struct(table_schema_nested: Schema) -> None:
    class TestStruct(StructProtocol):
        def __init__(self, pos: Dict[int, Any] = EMPTY_DICT):
            self._pos: Dict[int, Any] = pos

        def __setitem__(self, pos: int, value: Any) -> None:
            pass

        def __getitem__(self, pos: int) -> Any:
            return self._pos[pos]

    accessors = build_position_accessors(table_schema_nested)
    container = TestStruct({6: TestStruct({0: "name"})})
    inner_accessor = accessors.get(16)
    assert inner_accessor
    assert inner_accessor.get(container) == "name"


def test_serialize_schema(table_schema_with_full_nested_fields: Schema) -> None:
    actual = table_schema_with_full_nested_fields.model_dump_json()
    expected = """{"type":"struct","fields":[{"id":1,"name":"foo","type":"string","required":false,"doc":"foo doc","initial-default":"foo initial","write-default":"foo write"},{"id":2,"name":"bar","type":"int","required":true,"doc":"bar doc","initial-default":42,"write-default":43},{"id":3,"name":"baz","type":"boolean","required":false,"doc":"baz doc","initial-default":true,"write-default":false}],"schema-id":1,"identifier-field-ids":[2]}"""
    assert actual == expected


def test_deserialize_schema(table_schema_with_full_nested_fields: Schema) -> None:
    actual = Schema.model_validate_json(
        """{"type": "struct", "fields": [{"id": 1, "name": "foo", "type": "string", "required": false, "doc": "foo doc", "initial-default": "foo initial", "write-default": "foo write"}, {"id": 2, "name": "bar", "type": "int", "required": true, "doc": "bar doc", "initial-default": 42, "write-default": 43}, {"id": 3, "name": "baz", "type": "boolean", "required": false, "doc": "baz doc", "initial-default": true, "write-default": false}], "schema-id": 1, "identifier-field-ids": [2]}"""
    )
    expected = table_schema_with_full_nested_fields
    assert actual == expected


def test_sanitize() -> None:
    before_sanitized = Schema(
        NestedField(field_id=1, name="foo_field/bar", field_type=StringType(), required=True),
        NestedField(
            field_id=2,
            name="foo_list/bar",
            field_type=ListType(element_id=3, element_type=StringType(), element_required=True),
            required=True,
        ),
        NestedField(
            field_id=4,
            name="foo_map/bar",
            field_type=MapType(
                key_id=5,
                key_type=StringType(),
                value_id=6,
                value_type=MapType(key_id=7, key_type=StringType(), value_id=10, value_type=IntegerType(), value_required=True),
                value_required=True,
            ),
            required=True,
        ),
        NestedField(
            field_id=8,
            name="foo_struct/bar",
            field_type=StructType(
                NestedField(field_id=9, name="foo_struct_1/bar", field_type=StringType(), required=False),
                NestedField(field_id=10, name="foo_struct_2/bar", field_type=IntegerType(), required=True),
            ),
            required=False,
        ),
        NestedField(
            field_id=11,
            name="foo_list_2/bar",
            field_type=ListType(
                element_id=12,
                element_type=StructType(
                    NestedField(field_id=13, name="foo_list_2_1/bar", field_type=LongType(), required=True),
                    NestedField(field_id=14, name="foo_list_2_2/bar", field_type=LongType(), required=True),
                ),
                element_required=False,
            ),
            required=False,
        ),
        NestedField(
            field_id=15,
            name="foo_map_2/bar",
            field_type=MapType(
                key_id=16,
                value_id=17,
                key_type=StructType(
                    NestedField(field_id=18, name="foo_map_2_1/bar", field_type=StringType(), required=True),
                ),
                value_type=StructType(
                    NestedField(field_id=19, name="foo_map_2_2/bar", field_type=FloatType(), required=True),
                ),
                value_required=True,
            ),
            required=True,
        ),
        schema_id=1,
        identifier_field_ids=[1],
    )
    expected_schema = Schema(
        NestedField(field_id=1, name="foo_field_x2Fbar", field_type=StringType(), required=True),
        NestedField(
            field_id=2,
            name="foo_list_x2Fbar",
            field_type=ListType(element_id=3, element_type=StringType(), element_required=True),
            required=True,
        ),
        NestedField(
            field_id=4,
            name="foo_map_x2Fbar",
            field_type=MapType(
                key_id=5,
                key_type=StringType(),
                value_id=6,
                value_type=MapType(key_id=7, key_type=StringType(), value_id=10, value_type=IntegerType(), value_required=True),
                value_required=True,
            ),
            required=True,
        ),
        NestedField(
            field_id=8,
            name="foo_struct_x2Fbar",
            field_type=StructType(
                NestedField(field_id=9, name="foo_struct_1_x2Fbar", field_type=StringType(), required=False),
                NestedField(field_id=10, name="foo_struct_2_x2Fbar", field_type=IntegerType(), required=True),
            ),
            required=False,
        ),
        NestedField(
            field_id=11,
            name="foo_list_2_x2Fbar",
            field_type=ListType(
                element_id=12,
                element_type=StructType(
                    NestedField(field_id=13, name="foo_list_2_1_x2Fbar", field_type=LongType(), required=True),
                    NestedField(field_id=14, name="foo_list_2_2_x2Fbar", field_type=LongType(), required=True),
                ),
                element_required=False,
            ),
            required=False,
        ),
        NestedField(
            field_id=15,
            name="foo_map_2_x2Fbar",
            field_type=MapType(
                key_id=16,
                value_id=17,
                key_type=StructType(
                    NestedField(field_id=18, name="foo_map_2_1_x2Fbar", field_type=StringType(), required=True),
                ),
                value_type=StructType(
                    NestedField(field_id=19, name="foo_map_2_2_x2Fbar", field_type=FloatType(), required=True),
                ),
                value_required=True,
            ),
            required=True,
        ),
        schema_id=1,
        identifier_field_ids=[1],
    )
    assert sanitize_column_names(before_sanitized) == expected_schema


def test_prune_columns_string(table_schema_nested_with_struct_key_map: Schema) -> None:
    assert prune_columns(table_schema_nested_with_struct_key_map, {1}, False) == Schema(
        NestedField(field_id=1, name="foo", field_type=StringType(), required=True), schema_id=1, identifier_field_ids=[1]
    )


def test_prune_columns_string_full(table_schema_nested_with_struct_key_map: Schema) -> None:
    assert prune_columns(table_schema_nested_with_struct_key_map, {1}, True) == Schema(
        NestedField(field_id=1, name="foo", field_type=StringType(), required=True),
        schema_id=1,
        identifier_field_ids=[1],
    )


def test_prune_columns_list(table_schema_nested: Schema) -> None:
    assert prune_columns(table_schema_nested, {5}, False) == Schema(
        NestedField(
            field_id=4,
            name="qux",
            field_type=ListType(type="list", element_id=5, element_type=StringType(), element_required=True),
            required=True,
        ),
        schema_id=1,
        identifier_field_ids=[],
    )


def test_prune_columns_list_itself(table_schema_nested: Schema) -> None:
    with pytest.raises(ValueError) as exc_info:
        assert prune_columns(table_schema_nested, {4}, False)
    assert "Cannot explicitly project List or Map types, 4:qux of type list<string> was selected" in str(exc_info.value)


def test_prune_columns_list_full(table_schema_nested: Schema) -> None:
    assert prune_columns(table_schema_nested, {5}, True) == Schema(
        NestedField(
            field_id=4,
            name="qux",
            field_type=ListType(type="list", element_id=5, element_type=StringType(), element_required=True),
            required=True,
        ),
        schema_id=1,
        identifier_field_ids=[],
    )


def test_prune_columns_map(table_schema_nested: Schema) -> None:
    assert prune_columns(table_schema_nested, {9}, False) == Schema(
        NestedField(
            field_id=6,
            name="quux",
            field_type=MapType(
                type="map",
                key_id=7,
                key_type=StringType(),
                value_id=8,
                value_type=MapType(
                    type="map", key_id=9, key_type=StringType(), value_id=10, value_type=IntegerType(), value_required=True
                ),
                value_required=True,
            ),
            required=True,
        ),
        schema_id=1,
        identifier_field_ids=[],
    )


def test_prune_columns_map_itself(table_schema_nested: Schema) -> None:
    with pytest.raises(ValueError) as exc_info:
        assert prune_columns(table_schema_nested, {6}, False)
    assert "Cannot explicitly project List or Map types, 6:quux of type map<string, map<string, int>> was selected" in str(
        exc_info.value
    )


def test_prune_columns_map_full(table_schema_nested: Schema) -> None:
    assert prune_columns(table_schema_nested, {9}, True) == Schema(
        NestedField(
            field_id=6,
            name="quux",
            field_type=MapType(
                type="map",
                key_id=7,
                key_type=StringType(),
                value_id=8,
                value_type=MapType(
                    type="map", key_id=9, key_type=StringType(), value_id=10, value_type=IntegerType(), value_required=True
                ),
                value_required=True,
            ),
            required=True,
        ),
        schema_id=1,
        identifier_field_ids=[],
    )


def test_prune_columns_map_key(table_schema_nested: Schema) -> None:
    assert prune_columns(table_schema_nested, {10}, False) == Schema(
        NestedField(
            field_id=6,
            name="quux",
            field_type=MapType(
                type="map",
                key_id=7,
                key_type=StringType(),
                value_id=8,
                value_type=MapType(
                    type="map", key_id=9, key_type=StringType(), value_id=10, value_type=IntegerType(), value_required=True
                ),
                value_required=True,
            ),
            required=True,
        ),
        schema_id=1,
        identifier_field_ids=[],
    )


def test_prune_columns_struct(table_schema_nested: Schema) -> None:
    assert prune_columns(table_schema_nested, {16}, False) == Schema(
        NestedField(
            field_id=15,
            name="person",
            field_type=StructType(NestedField(field_id=16, name="name", field_type=StringType(), required=False)),
            required=False,
        ),
        schema_id=1,
        identifier_field_ids=[],
    )


def test_prune_columns_struct_full(table_schema_nested: Schema) -> None:
    actual = prune_columns(table_schema_nested, {16}, True)
    assert actual == Schema(
        NestedField(
            field_id=15,
            name="person",
            field_type=StructType(NestedField(field_id=16, name="name", field_type=StringType(), required=False)),
            required=False,
        ),
        schema_id=1,
        identifier_field_ids=[],
    )


def test_prune_columns_empty_struct() -> None:
    schema_empty_struct = Schema(
        NestedField(
            field_id=15,
            name="person",
            field_type=StructType(),
            required=False,
        )
    )
    assert prune_columns(schema_empty_struct, {15}, False) == Schema(
        NestedField(field_id=15, name="person", field_type=StructType(), required=False), schema_id=0, identifier_field_ids=[]
    )


def test_prune_columns_empty_struct_full() -> None:
    schema_empty_struct = Schema(
        NestedField(
            field_id=15,
            name="person",
            field_type=StructType(),
            required=False,
        )
    )
    assert prune_columns(schema_empty_struct, {15}, True) == Schema(
        NestedField(field_id=15, name="person", field_type=StructType(), required=False), schema_id=0, identifier_field_ids=[]
    )


def test_prune_columns_struct_in_map() -> None:
    table_schema_nested = Schema(
        NestedField(
            field_id=6,
            name="id_to_person",
            field_type=MapType(
                key_id=7,
                key_type=IntegerType(),
                value_id=8,
                value_type=StructType(
                    NestedField(field_id=10, name="name", field_type=StringType(), required=False),
                    NestedField(field_id=11, name="age", field_type=IntegerType(), required=True),
                ),
                value_required=True,
            ),
            required=True,
        ),
        schema_id=1,
        identifier_field_ids=[],
    )
    assert prune_columns(table_schema_nested, {11}, False) == Schema(
        NestedField(
            field_id=6,
            name="id_to_person",
            field_type=MapType(
                type="map",
                key_id=7,
                key_type=IntegerType(),
                value_id=8,
                value_type=StructType(NestedField(field_id=11, name="age", field_type=IntegerType(), required=True)),
                value_required=True,
            ),
            required=True,
        ),
        schema_id=1,
        identifier_field_ids=[],
    )


def test_prune_columns_struct_in_map_full() -> None:
    table_schema_nested = Schema(
        NestedField(
            field_id=6,
            name="id_to_person",
            field_type=MapType(
                key_id=7,
                key_type=IntegerType(),
                value_id=8,
                value_type=StructType(
                    NestedField(field_id=10, name="name", field_type=StringType(), required=False),
                    NestedField(field_id=11, name="age", field_type=IntegerType(), required=True),
                ),
                value_required=True,
            ),
            required=True,
        ),
        schema_id=1,
        identifier_field_ids=[],
    )
    assert prune_columns(table_schema_nested, {11}, True) == Schema(
        NestedField(
            field_id=6,
            name="id_to_person",
            field_type=MapType(
                type="map",
                key_id=7,
                key_type=IntegerType(),
                value_id=8,
                value_type=StructType(NestedField(field_id=11, name="age", field_type=IntegerType(), required=True)),
                value_required=True,
            ),
            required=True,
        ),
        schema_id=1,
        identifier_field_ids=[],
    )


def test_prune_columns_select_original_schema(table_schema_nested: Schema) -> None:
    ids = set(range(table_schema_nested.highest_field_id))
    assert prune_columns(table_schema_nested, ids, True) == table_schema_nested


def test_schema_select(table_schema_nested: Schema) -> None:
    assert table_schema_nested.select("bar", "baz") == Schema(
        NestedField(field_id=2, name="bar", field_type=IntegerType(), required=True),
        NestedField(field_id=3, name="baz", field_type=BooleanType(), required=False),
        schema_id=1,
        identifier_field_ids=[2],
    )


def test_schema_select_case_insensitive(table_schema_nested: Schema) -> None:
    assert table_schema_nested.select("BAZ", case_sensitive=False) == Schema(
        NestedField(field_id=3, name="baz", field_type=BooleanType(), required=False), schema_id=1, identifier_field_ids=[]
    )


def test_schema_select_cant_be_found(table_schema_nested: Schema) -> None:
    with pytest.raises(ValueError) as exc_info:
        table_schema_nested.select("BAZ", case_sensitive=True)
    assert "Could not find column: 'BAZ'" in str(exc_info.value)


def should_promote(file_type: IcebergType, read_type: IcebergType) -> bool:
    if isinstance(file_type, IntegerType) and isinstance(read_type, LongType):
        return True
    if isinstance(file_type, FloatType) and isinstance(read_type, DoubleType):
        return True
    if isinstance(file_type, StringType) and isinstance(read_type, BinaryType):
        return True
    if isinstance(file_type, BinaryType) and isinstance(read_type, StringType):
        return True
    if isinstance(file_type, DecimalType) and isinstance(read_type, DecimalType):
        return file_type.precision <= read_type.precision and file_type.scale == file_type.scale
    if isinstance(file_type, FixedType) and isinstance(read_type, UUIDType) and len(file_type) == 16:
        return True
    return False


def test_identifier_fields_fails(table_schema_nested_with_struct_key_map: Schema) -> None:
    with pytest.raises(ValueError) as exc_info:
        Schema(*table_schema_nested_with_struct_key_map.fields, schema_id=1, identifier_field_ids=[999])
    assert "Could not find field with id: 999" in str(exc_info.value)

    with pytest.raises(ValueError) as exc_info:
        Schema(*table_schema_nested_with_struct_key_map.fields, schema_id=1, identifier_field_ids=[11])
    assert "Identifier field 11 invalid: not a primitive type field" in str(exc_info.value)

    with pytest.raises(ValueError) as exc_info:
        Schema(*table_schema_nested_with_struct_key_map.fields, schema_id=1, identifier_field_ids=[3])
    assert "Identifier field 3 invalid: not a required field" in str(exc_info.value)

    with pytest.raises(ValueError) as exc_info:
        Schema(*table_schema_nested_with_struct_key_map.fields, schema_id=1, identifier_field_ids=[28])
    assert "Identifier field 28 invalid: must not be float or double field" in str(exc_info.value)

    with pytest.raises(ValueError) as exc_info:
        Schema(*table_schema_nested_with_struct_key_map.fields, schema_id=1, identifier_field_ids=[29])
    assert "Identifier field 29 invalid: must not be float or double field" in str(exc_info.value)

    with pytest.raises(ValueError) as exc_info:
        Schema(*table_schema_nested_with_struct_key_map.fields, schema_id=1, identifier_field_ids=[23])
    assert (
        f"Cannot add field zip as an identifier field: must not be nested in {table_schema_nested_with_struct_key_map.find_field('location')}"
        in str(exc_info.value)
    )

    with pytest.raises(ValueError) as exc_info:
        Schema(*table_schema_nested_with_struct_key_map.fields, schema_id=1, identifier_field_ids=[26])
    assert (
        f"Cannot add field x as an identifier field: must not be nested in {table_schema_nested_with_struct_key_map.find_field('points')}"
        in str(exc_info.value)
    )

    with pytest.raises(ValueError) as exc_info:
        Schema(*table_schema_nested_with_struct_key_map.fields, schema_id=1, identifier_field_ids=[17])
    assert (
        f"Cannot add field age as an identifier field: must not be nested in an optional field {table_schema_nested_with_struct_key_map.find_field('person')}"
        in str(exc_info.value)
    )


@pytest.mark.parametrize(
    "file_type",
    TEST_PRIMITIVE_TYPES,
)
@pytest.mark.parametrize(
    "read_type",
    TEST_PRIMITIVE_TYPES,
)
def test_promotion(file_type: IcebergType, read_type: IcebergType) -> None:
    if file_type == read_type:
        return
    if should_promote(file_type, read_type):
        assert promote(file_type, read_type) == read_type
    else:
        with pytest.raises(ResolveError):
            promote(file_type, read_type)


@pytest.fixture()
def primitive_fields() -> List[NestedField]:
    return [
        NestedField(field_id=1, name=str(primitive_type), field_type=primitive_type, required=False)
        for primitive_type in TEST_PRIMITIVE_TYPES
    ]


def test_add_top_level_primitives(primitive_fields: List[NestedField]) -> None:
    for primitive_field in primitive_fields:
        new_schema = Schema(primitive_field)
        applied = UpdateSchema(transaction=None, schema=Schema()).union_by_name(new_schema)._apply()  # type: ignore
        assert applied == new_schema


def test_add_top_level_list_of_primitives(primitive_fields: NestedField) -> None:
    for primitive_type in TEST_PRIMITIVE_TYPES:
        new_schema = Schema(
            NestedField(
                field_id=1,
                name="aList",
                field_type=ListType(element_id=2, element_type=primitive_type, element_required=False),
                required=False,
            )
        )
        applied = UpdateSchema(transaction=None, schema=Schema()).union_by_name(new_schema)._apply()  # type: ignore
        assert applied.as_struct() == new_schema.as_struct()


def test_add_top_level_map_of_primitives(primitive_fields: NestedField) -> None:
    for primitive_type in TEST_PRIMITIVE_TYPES:
        new_schema = Schema(
            NestedField(
                field_id=1,
                name="aMap",
                field_type=MapType(
                    key_id=2, key_type=primitive_type, value_id=3, value_type=primitive_type, value_required=False
                ),
                required=False,
            )
        )
        applied = UpdateSchema(transaction=None, schema=Schema()).union_by_name(new_schema)._apply()  # type: ignore
        assert applied.as_struct() == new_schema.as_struct()


def test_add_top_struct_of_primitives(primitive_fields: NestedField) -> None:
    for primitive_type in TEST_PRIMITIVE_TYPES:
        new_schema = Schema(
            NestedField(
                field_id=1,
                name="aStruct",
                field_type=StructType(NestedField(field_id=2, name="primitive", field_type=primitive_type, required=False)),
                required=False,
            )
        )
        applied = UpdateSchema(transaction=None, schema=Schema()).union_by_name(new_schema)._apply()  # type: ignore
        assert applied.as_struct() == new_schema.as_struct()


def test_add_nested_primitive(primitive_fields: NestedField) -> None:
    for primitive_type in TEST_PRIMITIVE_TYPES:
        current_schema = Schema(NestedField(field_id=1, name="aStruct", field_type=StructType(), required=False))
        new_schema = Schema(
            NestedField(
                field_id=1,
                name="aStruct",
                field_type=StructType(NestedField(field_id=2, name="primitive", field_type=primitive_type, required=False)),
                required=False,
            )
        )
        applied = UpdateSchema(None, None, schema=current_schema).union_by_name(new_schema)._apply()  # type: ignore
        assert applied.as_struct() == new_schema.as_struct()


def _primitive_fields(types: List[PrimitiveType], start_id: int = 0) -> List[NestedField]:
    fields = []
    for iceberg_type in types:
        fields.append(NestedField(field_id=start_id, name=str(iceberg_type), field_type=iceberg_type, required=False))
        start_id = start_id + 1

    return fields


def test_add_nested_primitives(primitive_fields: NestedField) -> None:
    current_schema = Schema(NestedField(field_id=1, name="aStruct", field_type=StructType(), required=False))
    new_schema = Schema(
        NestedField(
            field_id=1, name="aStruct", field_type=StructType(*_primitive_fields(TEST_PRIMITIVE_TYPES, 2)), required=False
        )
    )
    applied = UpdateSchema(transaction=None, schema=current_schema).union_by_name(new_schema)._apply()  # type: ignore
    assert applied.as_struct() == new_schema.as_struct()


def test_add_nested_lists(primitive_fields: NestedField) -> None:
    new_schema = Schema(
        NestedField(
            field_id=1,
            name="aList",
            type=ListType(
                element_id=2,
                element_type=ListType(
                    element_id=3,
                    element_type=ListType(
                        element_id=4,
                        element_type=ListType(
                            element_id=5,
                            element_type=ListType(
                                element_id=6,
                                element_type=ListType(
                                    element_id=7,
                                    element_type=ListType(
                                        element_id=8,
                                        element_type=ListType(element_id=9, element_type=DecimalType(precision=11, scale=20)),
                                        element_required=False,
                                    ),
                                    element_required=False,
                                ),
                                element_required=False,
                            ),
                            element_required=False,
                        ),
                        element_required=False,
                    ),
                    element_required=False,
                ),
                element_required=False,
            ),
            required=False,
        )
    )
    applied = UpdateSchema(transaction=None, schema=Schema()).union_by_name(new_schema)._apply()  # type: ignore
    assert applied.as_struct() == new_schema.as_struct()


def test_add_nested_struct(primitive_fields: NestedField) -> None:
    new_schema = Schema(
        NestedField(
            field_id=1,
            name="struct1",
            type=StructType(
                NestedField(
                    field_id=2,
                    name="struct2",
                    type=StructType(
                        NestedField(
                            field_id=3,
                            name="struct3",
                            type=StructType(
                                NestedField(
                                    field_id=4,
                                    name="struct4",
                                    type=StructType(
                                        NestedField(
                                            field_id=5,
                                            name="struct5",
                                            type=StructType(
                                                NestedField(
                                                    field_id=6,
                                                    name="struct6",
                                                    type=StructType(
                                                        NestedField(field_id=7, name="aString", field_type=StringType())
                                                    ),
                                                    required=False,
                                                )
                                            ),
                                            required=False,
                                        )
                                    ),
                                    required=False,
                                )
                            ),
                            required=False,
                        )
                    ),
                    required=False,
                )
            ),
            required=False,
        )
    )
    applied = UpdateSchema(transaction=None, schema=Schema()).union_by_name(new_schema)._apply()  # type: ignore
    assert applied.as_struct() == new_schema.as_struct()


def test_add_nested_maps(primitive_fields: NestedField) -> None:
    new_schema = Schema(
        NestedField(
            field_id=1,
            name="struct",
            field_type=MapType(
                key_id=2,
                value_id=3,
                key_type=StringType(),
                value_type=MapType(
                    key_id=4,
                    value_id=5,
                    key_type=StringType(),
                    value_type=MapType(
                        key_id=6,
                        value_id=7,
                        key_type=StringType(),
                        value_type=MapType(
                            key_id=8,
                            value_id=9,
                            key_type=StringType(),
                            value_type=MapType(
                                key_id=10,
                                value_id=11,
                                key_type=StringType(),
                                value_type=MapType(key_id=12, value_id=13, key_type=StringType(), value_type=StringType()),
                                value_required=False,
                            ),
                            value_required=False,
                        ),
                        value_required=False,
                    ),
                    value_required=False,
                ),
                value_required=False,
            ),
            required=False,
        )
    )
    applied = UpdateSchema(transaction=None, schema=Schema()).union_by_name(new_schema)._apply()  # type: ignore
    assert applied.as_struct() == new_schema.as_struct()


def test_detect_invalid_top_level_list() -> None:
    current_schema = Schema(
        NestedField(
            field_id=1,
            name="aList",
            field_type=ListType(element_id=2, element_type=StringType(), element_required=False),
            required=False,
        )
    )
    new_schema = Schema(
        NestedField(
            field_id=1,
            name="aList",
            field_type=ListType(element_id=2, element_type=DoubleType(), element_required=False),
            required=False,
        )
    )

    with pytest.raises(ValidationError, match="Cannot change column type: aList.element: string -> double"):
        _ = UpdateSchema(transaction=None, schema=current_schema).union_by_name(new_schema)._apply()  # type: ignore


def test_detect_invalid_top_level_maps() -> None:
    current_schema = Schema(
        NestedField(
            field_id=1,
            name="aMap",
            field_type=MapType(key_id=2, value_id=3, key_type=StringType(), value_type=StringType(), value_required=False),
            required=False,
        )
    )
    new_schema = Schema(
        NestedField(
            field_id=1,
            name="aMap",
            field_type=MapType(key_id=2, value_id=3, key_type=UUIDType(), value_type=StringType(), value_required=False),
            required=False,
        )
    )

    with pytest.raises(ValidationError, match="Cannot change column type: aMap.key: string -> uuid"):
        _ = UpdateSchema(transaction=None, schema=current_schema).union_by_name(new_schema)._apply()  # type: ignore


def test_allow_double_to_float() -> None:
    current_schema = Schema(NestedField(field_id=1, name="aCol", field_type=DoubleType(), required=False))
    new_schema = Schema(NestedField(field_id=1, name="aCol", field_type=FloatType(), required=False))

    applied = UpdateSchema(transaction=None, schema=current_schema).union_by_name(new_schema)._apply()  # type: ignore

    assert applied.as_struct() == current_schema.as_struct()
    assert len(applied.fields) == 1
    assert isinstance(applied.fields[0].field_type, DoubleType)


def test_promote_float_to_double() -> None:
    current_schema = Schema(NestedField(field_id=1, name="aCol", field_type=FloatType(), required=False))
    new_schema = Schema(NestedField(field_id=1, name="aCol", field_type=DoubleType(), required=False))

    applied = UpdateSchema(transaction=None, schema=current_schema).union_by_name(new_schema)._apply()  # type: ignore

    assert applied.as_struct() == new_schema.as_struct()
    assert len(applied.fields) == 1
    assert isinstance(applied.fields[0].field_type, DoubleType)


def test_allow_long_to_int() -> None:
    current_schema = Schema(NestedField(field_id=1, name="aCol", field_type=LongType(), required=False))
    new_schema = Schema(NestedField(field_id=1, name="aCol", field_type=IntegerType(), required=False))

    applied = UpdateSchema(transaction=None, schema=current_schema).union_by_name(new_schema)._apply()  # type: ignore

    assert applied.as_struct() == current_schema.as_struct()
    assert len(applied.fields) == 1
    assert isinstance(applied.fields[0].field_type, LongType)


def test_promote_int_to_long() -> None:
    current_schema = Schema(NestedField(field_id=1, name="aCol", field_type=IntegerType(), required=False))
    new_schema = Schema(NestedField(field_id=1, name="aCol", field_type=LongType(), required=False))

    applied = UpdateSchema(transaction=None, schema=current_schema).union_by_name(new_schema)._apply()  # type: ignore

    assert applied.as_struct() == new_schema.as_struct()
    assert len(applied.fields) == 1
    assert isinstance(applied.fields[0].field_type, LongType)


def test_detect_invalid_promotion_string_to_float() -> None:
    current_schema = Schema(NestedField(field_id=1, name="aCol", field_type=StringType(), required=False))
    new_schema = Schema(NestedField(field_id=1, name="aCol", field_type=FloatType(), required=False))

    with pytest.raises(ValidationError, match="Cannot change column type: aCol: string -> float"):
        _ = UpdateSchema(transaction=None, schema=current_schema).union_by_name(new_schema)._apply()  # type: ignore


# decimal(P,S) Fixed-point decimal; precision P, scale S -> Scale is fixed [1],
# precision must be 38 or less
def test_type_promote_decimal_to_fixed_scale_with_wider_precision() -> None:
    current_schema = Schema(NestedField(field_id=1, name="aCol", field_type=DecimalType(precision=20, scale=1), required=False))
    new_schema = Schema(NestedField(field_id=1, name="aCol", field_type=DecimalType(precision=22, scale=1), required=False))

    applied = UpdateSchema(transaction=None, schema=current_schema).union_by_name(new_schema)._apply()  # type: ignore

    assert applied.as_struct() == new_schema.as_struct()
    assert len(applied.fields) == 1
    field = applied.fields[0]
    decimal_type = field.field_type
    assert isinstance(decimal_type, DecimalType)
    assert decimal_type.precision == 22
    assert decimal_type.scale == 1


def test_add_nested_structs(primitive_fields: NestedField) -> None:
    schema = Schema(
        NestedField(
            field_id=1,
            name="struct1",
            field_type=StructType(
                NestedField(
                    field_id=2,
                    name="struct2",
                    field_type=StructType(
                        NestedField(
                            field_id=3,
                            name="list",
                            field_type=ListType(
                                element_id=4,
                                element_type=StructType(
                                    NestedField(field_id=5, name="value", field_type=StringType(), required=False)
                                ),
                                element_required=False,
                            ),
                            required=False,
                        )
                    ),
                    required=False,
                )
            ),
            required=False,
        )
    )
    new_schema = Schema(
        NestedField(
            field_id=1,
            name="struct1",
            field_type=StructType(
                NestedField(
                    field_id=2,
                    name="struct2",
                    field_type=StructType(
                        NestedField(
                            field_id=3,
                            name="list",
                            field_type=ListType(
                                element_id=4,
                                element_type=StructType(
                                    NestedField(field_id=5, name="time", field_type=TimeType(), required=False)
                                ),
                                element_required=False,
                            ),
                            required=False,
                        )
                    ),
                    required=False,
                )
            ),
            required=False,
        )
    )
    applied = UpdateSchema(transaction=None, schema=schema).union_by_name(new_schema)._apply()  # type: ignore

    expected = Schema(
        NestedField(
            field_id=1,
            name="struct1",
            field_type=StructType(
                NestedField(
                    field_id=2,
                    name="struct2",
                    field_type=StructType(
                        NestedField(
                            field_id=3,
                            name="list",
                            field_type=ListType(
                                element_id=4,
                                element_type=StructType(
                                    NestedField(field_id=5, name="value", field_type=StringType(), required=False),
                                    NestedField(field_id=6, name="time", field_type=TimeType(), required=False),
                                ),
                                element_required=False,
                            ),
                            required=False,
                        )
                    ),
                    required=False,
                )
            ),
            required=False,
        )
    )

    assert applied.as_struct() == expected.as_struct()


def test_replace_list_with_primitive() -> None:
    current_schema = Schema(NestedField(field_id=1, name="aCol", field_type=ListType(element_id=2, element_type=StringType())))
    new_schema = Schema(NestedField(field_id=1, name="aCol", field_type=StringType()))

    with pytest.raises(ValidationError, match="Cannot change column type: list<string> is not a primitive"):
        _ = UpdateSchema(transaction=None, schema=current_schema).union_by_name(new_schema)._apply()  # type: ignore


def test_mirrored_schemas() -> None:
    current_schema = Schema(
        NestedField(9, "struct1", StructType(NestedField(8, "string1", StringType(), required=False)), required=False),
        NestedField(6, "list1", ListType(element_id=7, element_type=StringType(), element_required=False), required=False),
        NestedField(5, "string2", StringType(), required=False),
        NestedField(4, "string3", StringType(), required=False),
        NestedField(3, "string4", StringType(), required=False),
        NestedField(2, "string5", StringType(), required=False),
        NestedField(1, "string6", StringType(), required=False),
    )
    mirrored_schema = Schema(
        NestedField(1, "struct1", StructType(NestedField(2, "string1", StringType(), required=False))),
        NestedField(3, "list1", ListType(element_id=4, element_type=StringType(), element_required=False), required=False),
        NestedField(5, "string2", StringType(), required=False),
        NestedField(6, "string3", StringType(), required=False),
        NestedField(7, "string4", StringType(), required=False),
        NestedField(8, "string5", StringType(), required=False),
        NestedField(9, "string6", StringType(), required=False),
    )

    applied = UpdateSchema(transaction=None, schema=current_schema).union_by_name(mirrored_schema)._apply()  # type: ignore

    assert applied.as_struct() == current_schema.as_struct()


def test_add_new_top_level_struct() -> None:
    current_schema = Schema(
        NestedField(
            1,
            "map1",
            MapType(
                key_id=2,
                value_id=3,
                key_type=StringType(),
                value_type=ListType(
                    element_id=4,
                    element_type=StructType(NestedField(field_id=5, name="string", field_type=StringType(), required=False)),
                ),
                value_required=False,
            ),
        )
    )
    observed_schema = Schema(
        NestedField(
            1,
            "map1",
            MapType(
                key_id=2,
                value_id=3,
                key_type=StringType(),
                value_type=ListType(
                    element_id=4,
                    element_type=StructType(NestedField(field_id=5, name="string", field_type=StringType(), required=False)),
                ),
                value_required=False,
            ),
        ),
        NestedField(
            field_id=6,
            name="struct1",
            field_type=StructType(
                NestedField(
                    field_id=7,
                    name="d1",
                    field_type=StructType(NestedField(field_id=8, name="d2", field_type=StringType(), required=False)),
                    required=False,
                )
            ),
            required=False,
        ),
    )

    applied = UpdateSchema(transaction=None, schema=current_schema).union_by_name(observed_schema)._apply()  # type: ignore

    assert applied.as_struct() == observed_schema.as_struct()


def test_append_nested_struct() -> None:
    current_schema = Schema(
        NestedField(
            field_id=1,
            name="s1",
            field_type=StructType(
                NestedField(
                    field_id=2,
                    name="s2",
                    field_type=StructType(
                        NestedField(
                            field_id=3,
                            name="s3",
                            field_type=StructType(NestedField(field_id=4, name="s4", field_type=StringType(), required=False)),
                        )
                    ),
                    required=False,
                )
            ),
        )
    )
    observed_schema = Schema(
        NestedField(
            field_id=1,
            name="s1",
            field_type=StructType(
                NestedField(
                    field_id=2,
                    name="s2",
                    field_type=StructType(
                        NestedField(
                            field_id=3,
                            name="s3",
                            field_type=StructType(NestedField(field_id=4, name="s4", field_type=StringType(), required=False)),
                            required=False,
                        ),
                        NestedField(
                            field_id=5,
                            name="repeat",
                            field_type=StructType(
                                NestedField(
                                    field_id=6,
                                    name="s1",
                                    field_type=StructType(
                                        NestedField(
                                            field_id=7,
                                            name="s2",
                                            field_type=StructType(
                                                NestedField(
                                                    field_id=8,
                                                    name="s3",
                                                    field_type=StructType(
                                                        NestedField(field_id=9, name="s4", field_type=StringType())
                                                    ),
                                                    required=False,
                                                )
                                            ),
                                            required=False,
                                        )
                                    ),
                                    required=False,
                                )
                            ),
                            required=False,
                        ),
                        required=False,
                    ),
                    required=False,
                )
            ),
            required=False,
        )
    )

    applied = UpdateSchema(transaction=None, schema=current_schema).union_by_name(observed_schema)._apply()  # type: ignore

    assert applied.as_struct() == observed_schema.as_struct()


def test_append_nested_lists() -> None:
    current_schema = Schema(
        NestedField(
            field_id=1,
            name="s1",
            field_type=StructType(
                NestedField(
                    field_id=2,
                    name="s2",
                    field_type=StructType(
                        NestedField(
                            field_id=3,
                            name="s3",
                            field_type=StructType(
                                NestedField(
                                    field_id=4,
                                    name="list1",
                                    field_type=ListType(element_id=5, element_type=StringType(), element_required=False),
                                    required=False,
                                )
                            ),
                            required=False,
                        )
                    ),
                    required=False,
                )
            ),
            required=False,
        )
    )

    observed_schema = Schema(
        NestedField(
            field_id=1,
            name="s1",
            field_type=StructType(
                NestedField(
                    field_id=2,
                    name="s2",
                    field_type=StructType(
                        NestedField(
                            field_id=3,
                            name="s3",
                            field_type=StructType(
                                NestedField(
                                    field_id=4,
                                    name="list2",
                                    field_type=ListType(element_id=5, element_type=StringType(), element_required=False),
                                    required=False,
                                )
                            ),
                            required=False,
                        )
                    ),
                    required=False,
                )
            ),
            required=False,
        )
    )
    union = UpdateSchema(transaction=None, schema=current_schema).union_by_name(observed_schema)._apply()  # type: ignore

    expected = Schema(
        NestedField(
            field_id=1,
            name="s1",
            field_type=StructType(
                NestedField(
                    field_id=2,
                    name="s2",
                    field_type=StructType(
                        NestedField(
                            field_id=3,
                            name="s3",
                            field_type=StructType(
                                NestedField(
                                    field_id=4,
                                    name="list1",
                                    field_type=ListType(element_id=5, element_type=StringType(), element_required=False),
                                    required=False,
                                ),
                                NestedField(
                                    field_id=6,
                                    name="list2",
                                    field_type=ListType(element_id=7, element_type=StringType(), element_required=False),
                                    required=False,
                                ),
                            ),
                            required=False,
                        )
                    ),
                    required=False,
                )
            ),
            required=False,
        )
    )

    assert union.as_struct() == expected.as_struct()


def test_union_with_pa_schema(primitive_fields: NestedField) -> None:
    base_schema = Schema(NestedField(field_id=1, name="foo", field_type=StringType(), required=True))

    pa_schema = pa.schema(
        [
            pa.field("foo", pa.string(), nullable=False),
            pa.field("bar", pa.int32(), nullable=True),
            pa.field("baz", pa.bool_(), nullable=True),
        ]
    )

    new_schema = UpdateSchema(transaction=None, schema=base_schema).union_by_name(pa_schema)._apply()  # type: ignore

    expected_schema = Schema(
        NestedField(field_id=1, name="foo", field_type=StringType(), required=True),
        NestedField(field_id=2, name="bar", field_type=IntegerType(), required=False),
        NestedField(field_id=3, name="baz", field_type=BooleanType(), required=False),
    )

    assert new_schema == expected_schema


def test_arrow_schema() -> None:
    base_schema = Schema(
        NestedField(field_id=1, name="foo", field_type=StringType(), required=True),
        NestedField(field_id=2, name="bar", field_type=IntegerType(), required=False),
        NestedField(field_id=3, name="baz", field_type=BooleanType(), required=False),
    )

    expected_schema = pa.schema(
        [
            pa.field("foo", pa.large_string(), nullable=False),
            pa.field("bar", pa.int32(), nullable=True),
            pa.field("baz", pa.bool_(), nullable=True),
        ]
    )

    assert base_schema.as_arrow() == expected_schema
