from decimal import Decimal
from uuid import uuid4

import boto3
import pytest
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from moto import mock_dynamodb


@mock_dynamodb
def test_get_item_without_range_key_boto3():
    client = boto3.resource("dynamodb", region_name="us-east-1")
    table = client.create_table(
        TableName="messages",
        KeySchema=[
            {"AttributeName": "id", "KeyType": "HASH"},
            {"AttributeName": "subject", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "subject", "AttributeType": "S"},
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 5},
    )

    hash_key = "3241526475"
    range_key = "1234567890987"
    table.put_item(Item={"id": hash_key, "subject": range_key})

    with pytest.raises(ClientError) as ex:
        table.get_item(Key={"id": hash_key})

    assert ex.value.response["Error"]["Code"] == "ValidationException"
    assert ex.value.response["Error"]["Message"] == "Validation Exception"


@mock_dynamodb
def test_query_filter_boto3():
    table_schema = {
        "KeySchema": [
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ],
    }

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.create_table(
        TableName="test-table", BillingMode="PAY_PER_REQUEST", **table_schema
    )

    for i in range(0, 3):
        table.put_item(Item={"pk": "pk", "sk": f"sk-{i}"})

    res = table.query(KeyConditionExpression=Key("pk").eq("pk"))
    assert len(res["Items"]) == 3

    res = table.query(KeyConditionExpression=Key("pk").eq("pk") & Key("sk").lt("sk-1"))
    assert len(res["Items"]) == 1
    assert res["Items"] == [{"pk": "pk", "sk": "sk-0"}]

    res = table.query(KeyConditionExpression=Key("pk").eq("pk") & Key("sk").lte("sk-1"))
    assert len(res["Items"]) == 2
    assert res["Items"] == [{"pk": "pk", "sk": "sk-0"}, {"pk": "pk", "sk": "sk-1"}]

    res = table.query(KeyConditionExpression=Key("pk").eq("pk") & Key("sk").gt("sk-1"))
    assert len(res["Items"]) == 1
    assert res["Items"] == [{"pk": "pk", "sk": "sk-2"}]

    res = table.query(KeyConditionExpression=Key("pk").eq("pk") & Key("sk").gte("sk-1"))
    assert len(res["Items"]) == 2
    assert res["Items"] == [{"pk": "pk", "sk": "sk-1"}, {"pk": "pk", "sk": "sk-2"}]


@mock_dynamodb
def test_boto3_conditions():
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

    # Create the DynamoDB table.
    table = dynamodb.create_table(
        TableName="users",
        KeySchema=[
            {"AttributeName": "forum_name", "KeyType": "HASH"},
            {"AttributeName": "subject", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "forum_name", "AttributeType": "S"},
            {"AttributeName": "subject", "AttributeType": "S"},
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    table = dynamodb.Table("users")

    table.put_item(Item={"forum_name": "the-key", "subject": "123"})
    table.put_item(Item={"forum_name": "the-key", "subject": "456"})
    table.put_item(Item={"forum_name": "the-key", "subject": "789"})

    # Test a query returning all items
    results = table.query(
        KeyConditionExpression=Key("forum_name").eq("the-key") & Key("subject").gt("1"),
        ScanIndexForward=True,
    )
    expected = ["123", "456", "789"]
    for index, item in enumerate(results["Items"]):
        assert item["subject"] == expected[index]

    # Return all items again, but in reverse
    results = table.query(
        KeyConditionExpression=Key("forum_name").eq("the-key") & Key("subject").gt("1"),
        ScanIndexForward=False,
    )
    for index, item in enumerate(reversed(results["Items"])):
        assert item["subject"] == expected[index]

    # Filter the subjects to only return some of the results
    results = table.query(
        KeyConditionExpression=Key("forum_name").eq("the-key")
        & Key("subject").gt("234"),
        ConsistentRead=True,
    )
    assert results["Count"] == 2

    # Filter to return no results
    results = table.query(
        KeyConditionExpression=Key("forum_name").eq("the-key")
        & Key("subject").gt("9999")
    )
    assert results["Count"] == 0

    results = table.query(
        KeyConditionExpression=Key("forum_name").eq("the-key")
        & Key("subject").begins_with("12")
    )
    assert results["Count"] == 1

    results = table.query(
        KeyConditionExpression=Key("subject").begins_with("7")
        & Key("forum_name").eq("the-key")
    )
    assert results["Count"] == 1

    results = table.query(
        KeyConditionExpression=Key("forum_name").eq("the-key")
        & Key("subject").between("567", "890")
    )
    assert results["Count"] == 1


@mock_dynamodb
def test_boto3_conditions_ignorecase():
    dynamodb = boto3.client("dynamodb", region_name="us-east-1")

    # Create the DynamoDB table.
    dynamodb.create_table(
        TableName="users",
        KeySchema=[
            {"AttributeName": "forum_name", "KeyType": "HASH"},
            {"AttributeName": "subject", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "forum_name", "AttributeType": "S"},
            {"AttributeName": "subject", "AttributeType": "S"},
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )

    dynamodb.put_item(
        TableName="users",
        Item={"forum_name": {"S": "the-key"}, "subject": {"S": "100"}},
    )
    dynamodb.put_item(
        TableName="users",
        Item={"forum_name": {"S": "the-key"}, "subject": {"S": "199"}},
    )
    dynamodb.put_item(
        TableName="users",
        Item={"forum_name": {"S": "the-key"}, "subject": {"S": "250"}},
    )

    between_expressions = [
        "BETWEEN :start  AND  :end",
        "between :start  and  :end",
        "Between :start  and  :end",
        "between :start  AnD  :end",
    ]
    for expr in between_expressions:
        results = dynamodb.query(
            TableName="users",
            KeyConditionExpression=f"forum_name = :forum_name and subject {expr}",
            ExpressionAttributeValues={
                ":forum_name": {"S": "the-key"},
                ":start": {"S": "100"},
                ":end": {"S": "200"},
            },
        )
        assert results["Count"] == 2

    with pytest.raises(ClientError) as ex:
        dynamodb.query(
            TableName="users",
            KeyConditionExpression="forum_name = :forum_name and BegIns_WiTh(subject, :subject )",
            ExpressionAttributeValues={
                ":forum_name": {"S": "the-key"},
                ":subject": {"S": "1"},
            },
        )
    assert ex.value.response["Error"]["Code"] == "ValidationException"
    assert (
        ex.value.response["Error"]["Message"]
        == "Invalid KeyConditionExpression: Invalid function name; function: BegIns_WiTh"
    )


@mock_dynamodb
def test_boto3_put_item_with_conditions():
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

    # Create the DynamoDB table.
    dynamodb.create_table(
        TableName="users",
        KeySchema=[
            {"AttributeName": "forum_name", "KeyType": "HASH"},
            {"AttributeName": "subject", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "forum_name", "AttributeType": "S"},
            {"AttributeName": "subject", "AttributeType": "S"},
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    table = dynamodb.Table("users")

    table.put_item(Item={"forum_name": "the-key", "subject": "123"})

    table.put_item(
        Item={"forum_name": "the-key-2", "subject": "1234"},
        ConditionExpression="attribute_not_exists(forum_name) AND attribute_not_exists(subject)",
    )

    with pytest.raises(ClientError) as exc:
        table.put_item(
            Item={"forum_name": "the-key", "subject": "123"},
            ConditionExpression="attribute_not_exists(forum_name) AND attribute_not_exists(subject)",
        )
    err = exc.value.response["Error"]
    assert err["Code"] == "ConditionalCheckFailedException"

    with pytest.raises(ClientError) as exc:
        table.put_item(
            Item={"forum_name": "bogus-key", "subject": "bogus", "test": "123"},
            ConditionExpression="attribute_exists(forum_name) AND attribute_exists(subject)",
        )
    err = exc.value.response["Error"]
    assert err["Code"] == "ConditionalCheckFailedException"


def _create_table_with_range_key():
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

    # Create the DynamoDB table.
    dynamodb.create_table(
        TableName="users",
        KeySchema=[
            {"AttributeName": "forum_name", "KeyType": "HASH"},
            {"AttributeName": "subject", "KeyType": "RANGE"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "TestGSI",
                "KeySchema": [
                    {"AttributeName": "username", "KeyType": "HASH"},
                    {"AttributeName": "created", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5,
                },
            }
        ],
        AttributeDefinitions=[
            {"AttributeName": "forum_name", "AttributeType": "S"},
            {"AttributeName": "subject", "AttributeType": "S"},
            {"AttributeName": "username", "AttributeType": "S"},
            {"AttributeName": "created", "AttributeType": "N"},
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    return dynamodb.Table("users")


@mock_dynamodb
def test_update_item_range_key_set():
    table = _create_table_with_range_key()
    table.put_item(
        Item={
            "forum_name": "the-key",
            "subject": "123",
            "username": "johndoe",
            "created": Decimal("3"),
        }
    )

    item_key = {"forum_name": "the-key", "subject": "123"}
    table.update_item(
        Key=item_key,
        AttributeUpdates={
            "username": {"Action": "PUT", "Value": "johndoe2"},
            "created": {"Action": "PUT", "Value": Decimal("4")},
            "mapfield": {"Action": "PUT", "Value": {"key": "value"}},
        },
    )

    returned_item = dict(
        (k, str(v) if isinstance(v, Decimal) else v)
        for k, v in table.get_item(Key=item_key)["Item"].items()
    )
    assert returned_item == {
        "username": "johndoe2",
        "forum_name": "the-key",
        "subject": "123",
        "created": "4",
        "mapfield": {"key": "value"},
    }


@mock_dynamodb
def test_update_item_does_not_exist_is_created():
    table = _create_table_with_range_key()

    item_key = {"forum_name": "the-key", "subject": "123"}
    result = table.update_item(
        Key=item_key,
        AttributeUpdates={
            "username": {"Action": "PUT", "Value": "johndoe2"},
            "created": {"Action": "PUT", "Value": Decimal("4")},
            "mapfield": {"Action": "PUT", "Value": {"key": "value"}},
        },
        ReturnValues="ALL_OLD",
    )

    assert not result.get("Attributes")

    returned_item = dict(
        (k, str(v) if isinstance(v, Decimal) else v)
        for k, v in table.get_item(Key=item_key)["Item"].items()
    )
    assert returned_item == {
        "username": "johndoe2",
        "forum_name": "the-key",
        "subject": "123",
        "created": "4",
        "mapfield": {"key": "value"},
    }


@mock_dynamodb
def test_update_item_add_value():
    table = _create_table_with_range_key()

    table.put_item(
        Item={"forum_name": "the-key", "subject": "123", "numeric_field": Decimal("-1")}
    )

    item_key = {"forum_name": "the-key", "subject": "123"}
    table.update_item(
        Key=item_key,
        AttributeUpdates={"numeric_field": {"Action": "ADD", "Value": Decimal("2")}},
    )

    returned_item = dict(
        (k, str(v) if isinstance(v, Decimal) else v)
        for k, v in table.get_item(Key=item_key)["Item"].items()
    )
    assert returned_item == {
        "numeric_field": "1",
        "forum_name": "the-key",
        "subject": "123",
    }


@mock_dynamodb
def test_update_item_add_value_string_set():
    table = _create_table_with_range_key()

    table.put_item(
        Item={
            "forum_name": "the-key",
            "subject": "123",
            "string_set": set(["str1", "str2"]),
        }
    )

    item_key = {"forum_name": "the-key", "subject": "123"}
    table.update_item(
        Key=item_key,
        AttributeUpdates={"string_set": {"Action": "ADD", "Value": set(["str3"])}},
    )

    returned_item = dict(
        (k, str(v) if isinstance(v, Decimal) else v)
        for k, v in table.get_item(Key=item_key)["Item"].items()
    )
    assert returned_item == {
        "string_set": set(["str1", "str2", "str3"]),
        "forum_name": "the-key",
        "subject": "123",
    }


@mock_dynamodb
def test_update_item_delete_value_string_set():
    table = _create_table_with_range_key()

    table.put_item(
        Item={
            "forum_name": "the-key",
            "subject": "123",
            "string_set": set(["str1", "str2"]),
        }
    )

    item_key = {"forum_name": "the-key", "subject": "123"}
    table.update_item(
        Key=item_key,
        AttributeUpdates={"string_set": {"Action": "DELETE", "Value": set(["str2"])}},
    )

    returned_item = dict(
        (k, str(v) if isinstance(v, Decimal) else v)
        for k, v in table.get_item(Key=item_key)["Item"].items()
    )
    assert returned_item == {
        "string_set": set(["str1"]),
        "forum_name": "the-key",
        "subject": "123",
    }


@mock_dynamodb
def test_update_item_add_value_does_not_exist_is_created():
    table = _create_table_with_range_key()

    item_key = {"forum_name": "the-key", "subject": "123"}
    table.update_item(
        Key=item_key,
        AttributeUpdates={"numeric_field": {"Action": "ADD", "Value": Decimal("2")}},
    )

    returned_item = dict(
        (k, str(v) if isinstance(v, Decimal) else v)
        for k, v in table.get_item(Key=item_key)["Item"].items()
    )
    assert returned_item == {
        "numeric_field": "2",
        "forum_name": "the-key",
        "subject": "123",
    }


@mock_dynamodb
def test_update_item_with_expression():
    table = _create_table_with_range_key()

    table.put_item(Item={"forum_name": "the-key", "subject": "123", "field": "1"})

    item_key = {"forum_name": "the-key", "subject": "123"}

    table.update_item(
        Key=item_key,
        UpdateExpression="SET field = :field_value",
        ExpressionAttributeValues={":field_value": 2},
    )
    assert table.get_item(Key=item_key)["Item"] == {
        "field": Decimal("2"),
        "forum_name": "the-key",
        "subject": "123",
    }

    table.update_item(
        Key=item_key,
        UpdateExpression="SET field = :field_value",
        ExpressionAttributeValues={":field_value": 3},
    )
    assert table.get_item(Key=item_key)["Item"] == {
        "field": Decimal("3"),
        "forum_name": "the-key",
        "subject": "123",
    }


def assert_failure_due_to_key_not_in_schema(func, **kwargs):
    with pytest.raises(ClientError) as ex:
        func(**kwargs)
    err = ex.value.response["Error"]
    assert err["Code"] == "ValidationException"
    assert err["Message"] == "The provided key element does not match the schema"


@mock_dynamodb
def test_update_item_add_with_expression():
    table = _create_table_with_range_key()

    item_key = {"forum_name": "the-key", "subject": "123"}
    current_item = {
        "forum_name": "the-key",
        "subject": "123",
        "str_set": {"item1", "item2", "item3"},
        "num_set": {1, 2, 3},
        "num_val": 6,
    }

    # Put an entry in the DB to play with
    table.put_item(Item=current_item)

    # Update item to add a string value to a string set
    table.update_item(
        Key=item_key,
        UpdateExpression="ADD str_set :v",
        ExpressionAttributeValues={":v": {"item4"}},
    )
    current_item["str_set"] = current_item["str_set"].union({"item4"})
    assert table.get_item(Key=item_key)["Item"] == current_item

    # Update item to add a string value to a non-existing set
    table.update_item(
        Key=item_key,
        UpdateExpression="ADD non_existing_str_set :v",
        ExpressionAttributeValues={":v": {"item4"}},
    )
    current_item["non_existing_str_set"] = {"item4"}
    assert table.get_item(Key=item_key)["Item"] == current_item

    # Update item to add a num value to a num set
    table.update_item(
        Key=item_key,
        UpdateExpression="ADD num_set :v",
        ExpressionAttributeValues={":v": {6}},
    )
    current_item["num_set"] = current_item["num_set"].union({6})
    assert table.get_item(Key=item_key)["Item"] == current_item

    # Update item to add a value to a number value
    table.update_item(
        Key=item_key,
        UpdateExpression="ADD num_val :v",
        ExpressionAttributeValues={":v": 20},
    )
    current_item["num_val"] = current_item["num_val"] + 20
    assert table.get_item(Key=item_key)["Item"] == current_item

    # Attempt to add a number value to a string set
    with pytest.raises(ClientError) as exc:
        table.update_item(
            Key=item_key,
            UpdateExpression="ADD str_set :v",
            ExpressionAttributeValues={":v": 20},
        )
    err = exc.value.response["Error"]
    assert (
        err["Message"]
        == "An operand in the update expression has an incorrect data type"
    )

    assert table.get_item(Key=item_key)["Item"] == current_item

    # Attempt to add a number set to the string set
    with pytest.raises(ClientError) as exc:
        table.update_item(
            Key=item_key,
            UpdateExpression="ADD str_set :v",
            ExpressionAttributeValues={":v": {20}},
        )
    err = exc.value.response["Error"]
    assert (
        err["Message"]
        == "An operand in the update expression has an incorrect data type"
    )

    assert table.get_item(Key=item_key)["Item"] == current_item

    # Attempt to update with a bad expression
    with pytest.raises(ClientError) as exc:
        table.update_item(Key=item_key, UpdateExpression="ADD str_set bad_value")
    err = exc.value.response["Error"]
    assert (
        err["Message"]
        == 'Invalid UpdateExpression: Syntax error; token: "bad_value", near: "str_set bad_value"'
    )

    # Attempt to add a string value instead of a string set
    with pytest.raises(ClientError) as exc:
        table.update_item(
            Key=item_key,
            UpdateExpression="ADD str_set :v",
            ExpressionAttributeValues={":v": "new_string"},
        )
    err = exc.value.response["Error"]
    assert (
        err["Message"]
        == "An operand in the update expression has an incorrect data type"
    )


@mock_dynamodb
def test_update_item_add_with_nested_sets():
    table = _create_table_with_range_key()

    item_key = {"forum_name": "the-key", "subject": "123"}
    current_item = {
        "forum_name": "the-key",
        "subject": "123",
        "nested": {"str_set": {"item1", "item2", "item3"}},
    }

    # Put an entry in the DB to play with
    table.put_item(Item=current_item)

    # Update item to add a string value to a nested string set
    table.update_item(
        Key=item_key,
        UpdateExpression="ADD nested.str_set :v",
        ExpressionAttributeValues={":v": {"item4"}},
    )
    current_item["nested"]["str_set"] = current_item["nested"]["str_set"].union(
        {"item4"}
    )
    assert table.get_item(Key=item_key)["Item"] == current_item

    # Update item to add a string value to a non-existing set
    table.update_item(
        Key=item_key,
        UpdateExpression="ADD #ns.#ne :v",
        ExpressionAttributeNames={"#ns": "nested", "#ne": "non_existing_str_set"},
        ExpressionAttributeValues={":v": {"new_item"}},
    )
    current_item["nested"]["non_existing_str_set"] = {"new_item"}
    assert table.get_item(Key=item_key)["Item"] == current_item


@mock_dynamodb
def test_update_item_delete_with_nested_sets():
    table = _create_table_with_range_key()

    item_key = {"forum_name": "the-key", "subject": "123"}
    current_item = {
        "forum_name": "the-key",
        "subject": "123",
        "nested": {"str_set": {"item1", "item2", "item3"}},
    }

    # Put an entry in the DB to play with
    table.put_item(Item=current_item)

    # Update item to add a string value to a nested string set
    table.update_item(
        Key=item_key,
        UpdateExpression="DELETE nested.str_set :v",
        ExpressionAttributeValues={":v": {"item3"}},
    )
    current_item["nested"]["str_set"] = current_item["nested"]["str_set"].difference(
        {"item3"}
    )
    assert table.get_item(Key=item_key)["Item"] == current_item


@mock_dynamodb
def test_update_item_delete_with_expression():
    table = _create_table_with_range_key()

    item_key = {"forum_name": "the-key", "subject": "123"}
    current_item = {
        "forum_name": "the-key",
        "subject": "123",
        "str_set": {"item1", "item2", "item3"},
        "num_set": {1, 2, 3},
        "num_val": 6,
    }

    # Put an entry in the DB to play with
    table.put_item(Item=current_item)

    # Update item to delete a string value from a string set
    table.update_item(
        Key=item_key,
        UpdateExpression="DELETE str_set :v",
        ExpressionAttributeValues={":v": {"item2"}},
    )
    current_item["str_set"] = current_item["str_set"].difference({"item2"})
    assert table.get_item(Key=item_key)["Item"] == current_item

    # Update item to delete  a num value from a num set
    table.update_item(
        Key=item_key,
        UpdateExpression="DELETE num_set :v",
        ExpressionAttributeValues={":v": {2}},
    )
    current_item["num_set"] = current_item["num_set"].difference({2})
    assert table.get_item(Key=item_key)["Item"] == current_item

    # Try to delete on a number, this should fail
    with pytest.raises(ClientError) as exc:
        table.update_item(
            Key=item_key,
            UpdateExpression="DELETE num_val :v",
            ExpressionAttributeValues={":v": 20},
        )
    err = exc.value.response["Error"]
    assert (
        err["Message"]
        == "Invalid UpdateExpression: Incorrect operand type for operator or function; operator or function: operator: DELETE, operand type: NUMBER"
    )

    assert table.get_item(Key=item_key)["Item"] == current_item

    # Try to delete a string set from a number set
    with pytest.raises(ClientError) as exc:
        table.update_item(
            Key=item_key,
            UpdateExpression="DELETE num_set :v",
            ExpressionAttributeValues={":v": {"del_str"}},
        )
    err = exc.value.response["Error"]
    assert (
        err["Message"]
        == "An operand in the update expression has an incorrect data type"
    )

    assert table.get_item(Key=item_key)["Item"] == current_item

    # Attempt to update with a bad expression
    with pytest.raises(ClientError) as exc:
        table.update_item(Key=item_key, UpdateExpression="DELETE num_val badvalue")
    err = exc.value.response["Error"]
    assert (
        err["Message"]
        == 'Invalid UpdateExpression: Syntax error; token: "badvalue", near: "num_val badvalue"'
    )


@mock_dynamodb
def test_boto3_query_gsi_range_comparison():
    table = _create_table_with_range_key()

    table.put_item(
        Item={
            "forum_name": "the-key",
            "subject": "123",
            "username": "johndoe",
            "created": 3,
        }
    )
    table.put_item(
        Item={
            "forum_name": "the-key",
            "subject": "456",
            "username": "johndoe",
            "created": 1,
        }
    )
    table.put_item(
        Item={
            "forum_name": "the-key",
            "subject": "789",
            "username": "johndoe",
            "created": 2,
        }
    )
    table.put_item(
        Item={
            "forum_name": "the-key",
            "subject": "159",
            "username": "janedoe",
            "created": 2,
        }
    )
    table.put_item(
        Item={
            "forum_name": "the-key",
            "subject": "601",
            "username": "janedoe",
            "created": 5,
        }
    )

    # Test a query returning all johndoe items
    results = table.query(
        KeyConditionExpression=Key("username").eq("johndoe") & Key("created").gt(0),
        ScanIndexForward=True,
        IndexName="TestGSI",
    )
    expected = ["456", "789", "123"]
    for index, item in enumerate(results["Items"]):
        assert item["subject"] == expected[index]

    # Return all johndoe items again, but in reverse
    results = table.query(
        KeyConditionExpression=Key("username").eq("johndoe") & Key("created").gt(0),
        ScanIndexForward=False,
        IndexName="TestGSI",
    )
    for index, item in enumerate(reversed(results["Items"])):
        assert item["subject"] == expected[index]

    # Filter the creation to only return some of the results
    # And reverse order of hash + range key
    results = table.query(
        KeyConditionExpression=Key("created").gt(1) & Key("username").eq("johndoe"),
        ConsistentRead=True,
        IndexName="TestGSI",
    )
    assert results["Count"] == 2

    # Filter to return no results
    results = table.query(
        KeyConditionExpression=Key("username").eq("janedoe") & Key("created").gt(9),
        IndexName="TestGSI",
    )
    assert results["Count"] == 0

    results = table.query(
        KeyConditionExpression=Key("username").eq("janedoe") & Key("created").eq(5),
        IndexName="TestGSI",
    )
    assert results["Count"] == 1

    # Test range key sorting
    results = table.query(
        KeyConditionExpression=Key("username").eq("johndoe") & Key("created").gt(0),
        IndexName="TestGSI",
    )
    expected = [Decimal("1"), Decimal("2"), Decimal("3")]
    for index, item in enumerate(results["Items"]):
        assert item["created"] == expected[index]


@mock_dynamodb
def test_boto3_update_table_throughput():
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

    # Create the DynamoDB table.
    table = dynamodb.create_table(
        TableName="users",
        KeySchema=[
            {"AttributeName": "forum_name", "KeyType": "HASH"},
            {"AttributeName": "subject", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "forum_name", "AttributeType": "S"},
            {"AttributeName": "subject", "AttributeType": "S"},
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 6},
    )
    table = dynamodb.Table("users")

    assert table.provisioned_throughput["ReadCapacityUnits"] == 5
    assert table.provisioned_throughput["WriteCapacityUnits"] == 6

    table.update(
        ProvisionedThroughput={"ReadCapacityUnits": 10, "WriteCapacityUnits": 11}
    )

    table = dynamodb.Table("users")

    assert table.provisioned_throughput["ReadCapacityUnits"] == 10
    assert table.provisioned_throughput["WriteCapacityUnits"] == 11


@mock_dynamodb
def test_boto3_update_table_gsi_throughput():
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

    # Create the DynamoDB table.
    table = dynamodb.create_table(
        TableName="users",
        KeySchema=[
            {"AttributeName": "forum_name", "KeyType": "HASH"},
            {"AttributeName": "subject", "KeyType": "RANGE"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "TestGSI",
                "KeySchema": [
                    {"AttributeName": "username", "KeyType": "HASH"},
                    {"AttributeName": "created", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 3,
                    "WriteCapacityUnits": 4,
                },
            }
        ],
        AttributeDefinitions=[
            {"AttributeName": "forum_name", "AttributeType": "S"},
            {"AttributeName": "subject", "AttributeType": "S"},
            {"AttributeName": "username", "AttributeType": "S"},
            {"AttributeName": "created", "AttributeType": "S"},
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 6},
    )
    table = dynamodb.Table("users")

    gsi_throughput = table.global_secondary_indexes[0]["ProvisionedThroughput"]
    assert gsi_throughput["ReadCapacityUnits"] == 3
    assert gsi_throughput["WriteCapacityUnits"] == 4

    assert table.provisioned_throughput["ReadCapacityUnits"] == 5
    assert table.provisioned_throughput["WriteCapacityUnits"] == 6

    table.update(
        GlobalSecondaryIndexUpdates=[
            {
                "Update": {
                    "IndexName": "TestGSI",
                    "ProvisionedThroughput": {
                        "ReadCapacityUnits": 10,
                        "WriteCapacityUnits": 11,
                    },
                }
            }
        ]
    )

    table = dynamodb.Table("users")

    # Primary throughput has not changed
    assert table.provisioned_throughput["ReadCapacityUnits"] == 5
    assert table.provisioned_throughput["WriteCapacityUnits"] == 6

    gsi_throughput = table.global_secondary_indexes[0]["ProvisionedThroughput"]
    assert gsi_throughput["ReadCapacityUnits"] == 10
    assert gsi_throughput["WriteCapacityUnits"] == 11


@mock_dynamodb
def test_update_table_gsi_create():
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

    # Create the DynamoDB table.
    table = dynamodb.create_table(
        TableName="users",
        KeySchema=[
            {"AttributeName": "forum_name", "KeyType": "HASH"},
            {"AttributeName": "subject", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "forum_name", "AttributeType": "S"},
            {"AttributeName": "subject", "AttributeType": "S"},
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 6},
    )
    table = dynamodb.Table("users")

    assert len(table.global_secondary_indexes) == 0
    assert len(table.attribute_definitions) == 2

    table.update(
        AttributeDefinitions=[
            {"AttributeName": "forum_name", "AttributeType": "S"},
            {"AttributeName": "subject", "AttributeType": "S"},
            {"AttributeName": "username", "AttributeType": "S"},
            {"AttributeName": "created", "AttributeType": "N"},
        ],
        GlobalSecondaryIndexUpdates=[
            {
                "Create": {
                    "IndexName": "TestGSI",
                    "KeySchema": [
                        {"AttributeName": "username", "KeyType": "HASH"},
                        {"AttributeName": "created", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {
                        "ReadCapacityUnits": 3,
                        "WriteCapacityUnits": 4,
                    },
                }
            }
        ],
    )

    table = dynamodb.Table("users")
    table.reload()
    assert len(table.global_secondary_indexes) == 1
    assert len(table.attribute_definitions) == 4

    gsi_throughput = table.global_secondary_indexes[0]["ProvisionedThroughput"]
    assert gsi_throughput["ReadCapacityUnits"] == 3
    assert gsi_throughput["WriteCapacityUnits"] == 4

    # Check update works
    table.update(
        GlobalSecondaryIndexUpdates=[
            {
                "Update": {
                    "IndexName": "TestGSI",
                    "ProvisionedThroughput": {
                        "ReadCapacityUnits": 10,
                        "WriteCapacityUnits": 11,
                    },
                }
            }
        ]
    )
    table = dynamodb.Table("users")

    gsi_throughput = table.global_secondary_indexes[0]["ProvisionedThroughput"]
    assert gsi_throughput["ReadCapacityUnits"] == 10
    assert gsi_throughput["WriteCapacityUnits"] == 11

    table.update(GlobalSecondaryIndexUpdates=[{"Delete": {"IndexName": "TestGSI"}}])

    table = dynamodb.Table("users")
    assert len(table.global_secondary_indexes) == 0


@mock_dynamodb
def test_update_table_gsi_throughput():
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

    # Create the DynamoDB table.
    table = dynamodb.create_table(
        TableName="users",
        KeySchema=[
            {"AttributeName": "forum_name", "KeyType": "HASH"},
            {"AttributeName": "subject", "KeyType": "RANGE"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "TestGSI",
                "KeySchema": [
                    {"AttributeName": "username", "KeyType": "HASH"},
                    {"AttributeName": "created", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 3,
                    "WriteCapacityUnits": 4,
                },
            }
        ],
        AttributeDefinitions=[
            {"AttributeName": "forum_name", "AttributeType": "S"},
            {"AttributeName": "subject", "AttributeType": "S"},
            {"AttributeName": "username", "AttributeType": "S"},
            {"AttributeName": "created", "AttributeType": "S"},
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 6},
    )
    table = dynamodb.Table("users")
    assert len(table.global_secondary_indexes) == 1

    table.update(GlobalSecondaryIndexUpdates=[{"Delete": {"IndexName": "TestGSI"}}])

    table = dynamodb.Table("users")
    assert len(table.global_secondary_indexes) == 0


@mock_dynamodb
def test_query_pagination():
    table = _create_table_with_range_key()
    for i in range(10):
        table.put_item(
            Item={
                "forum_name": "the-key",
                "subject": f"{i}",
                "username": "johndoe",
                "created": Decimal("3"),
            }
        )

    page1 = table.query(KeyConditionExpression=Key("forum_name").eq("the-key"), Limit=6)
    assert page1["Count"] == 6
    assert len(page1["Items"]) == 6

    page2 = table.query(
        KeyConditionExpression=Key("forum_name").eq("the-key"),
        Limit=6,
        ExclusiveStartKey=page1["LastEvaluatedKey"],
    )
    assert page2["Count"] == 4
    assert len(page2["Items"]) == 4
    assert "LastEvaluatedKey" not in page2

    results = page1["Items"] + page2["Items"]
    subjects = set([int(r["subject"]) for r in results])
    assert subjects == set(range(10))


@mock_dynamodb
def test_scan_by_index():
    dynamodb = boto3.client("dynamodb", region_name="us-east-1")

    dynamodb.create_table(
        TableName="test",
        KeySchema=[
            {"AttributeName": "id", "KeyType": "HASH"},
            {"AttributeName": "range_key", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "range_key", "AttributeType": "S"},
            {"AttributeName": "gsi_col", "AttributeType": "S"},
            {"AttributeName": "gsi_range_key", "AttributeType": "S"},
            {"AttributeName": "lsi_range_key", "AttributeType": "S"},
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
        GlobalSecondaryIndexes=[
            {
                "IndexName": "test_gsi",
                "KeySchema": [
                    {"AttributeName": "gsi_col", "KeyType": "HASH"},
                    {"AttributeName": "gsi_range_key", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 1,
                    "WriteCapacityUnits": 1,
                },
            }
        ],
        LocalSecondaryIndexes=[
            {
                "IndexName": "test_lsi",
                "KeySchema": [
                    {"AttributeName": "id", "KeyType": "HASH"},
                    {"AttributeName": "lsi_range_key", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )

    dynamodb.put_item(
        TableName="test",
        Item={
            "id": {"S": "1"},
            "range_key": {"S": "1"},
            "col1": {"S": "val1"},
            "gsi_col": {"S": "1"},
            "gsi_range_key": {"S": "1"},
            "lsi_range_key": {"S": "1"},
        },
    )

    dynamodb.put_item(
        TableName="test",
        Item={
            "id": {"S": "1"},
            "range_key": {"S": "2"},
            "col1": {"S": "val2"},
            "gsi_col": {"S": "1"},
            "gsi_range_key": {"S": "2"},
            "lsi_range_key": {"S": "2"},
        },
    )

    dynamodb.put_item(
        TableName="test",
        Item={"id": {"S": "3"}, "range_key": {"S": "1"}, "col1": {"S": "val3"}},
    )

    res = dynamodb.scan(TableName="test")
    assert res["Count"] == 3
    assert len(res["Items"]) == 3

    res = dynamodb.scan(TableName="test", Limit=1)
    assert res["Count"] == 1
    assert res["ScannedCount"] == 1

    res = dynamodb.scan(TableName="test", ExclusiveStartKey=res["LastEvaluatedKey"])
    assert res["Count"] == 2
    assert res["ScannedCount"] == 2

    res = dynamodb.scan(TableName="test", IndexName="test_gsi")
    assert res["Count"] == 2
    assert res["ScannedCount"] == 2
    assert len(res["Items"]) == 2

    res = dynamodb.scan(TableName="test", IndexName="test_gsi", Limit=1)
    assert res["Count"] == 1
    assert res["ScannedCount"] == 1
    assert len(res["Items"]) == 1
    last_eval_key = res["LastEvaluatedKey"]
    assert last_eval_key["id"]["S"] == "1"
    assert last_eval_key["gsi_col"]["S"] == "1"
    assert last_eval_key["gsi_range_key"]["S"] == "1"

    res = dynamodb.scan(
        TableName="test", IndexName="test_gsi", ExclusiveStartKey=last_eval_key
    )
    assert res["Count"] == 1
    assert res["ScannedCount"] == 1

    res = dynamodb.scan(TableName="test", IndexName="test_lsi")
    assert res["Count"] == 2
    assert res["ScannedCount"] == 2
    assert len(res["Items"]) == 2

    res = dynamodb.scan(TableName="test", IndexName="test_lsi", Limit=1)
    assert res["Count"] == 1
    assert res["ScannedCount"] == 1
    assert len(res["Items"]) == 1
    last_eval_key = res["LastEvaluatedKey"]
    assert last_eval_key["id"]["S"] == "1"
    assert last_eval_key["range_key"]["S"] == "1"
    assert last_eval_key["lsi_range_key"]["S"] == "1"


@mock_dynamodb
@pytest.mark.parametrize("create_item_first", [False, True])
@pytest.mark.parametrize(
    "expression", ["set h=:New", "set r=:New", "set x=:New, r=:New"]
)
def test_update_item_throws_exception_when_updating_hash_or_range_key(
    create_item_first, expression
):
    client = boto3.client("dynamodb", region_name="ap-northeast-3")
    table_name = "testtable_3877"

    client.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "h", "KeyType": "HASH"},
            {"AttributeName": "r", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "h", "AttributeType": "S"},
            {"AttributeName": "r", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    initial_val = str(uuid4())

    if create_item_first:
        client.put_item(
            TableName=table_name, Item={"h": {"S": initial_val}, "r": {"S": "1"}}
        )

    # Updating the HASH key should fail
    with pytest.raises(ClientError) as ex:
        client.update_item(
            TableName=table_name,
            Key={"h": {"S": initial_val}, "r": {"S": "1"}},
            UpdateExpression=expression,
            ExpressionAttributeValues={":New": {"S": "2"}},
        )
    err = ex.value.response["Error"]
    assert err["Code"] == "ValidationException"
    assert "Cannot update attribute" in err["Message"]
    assert "This attribute is part of the key" in err["Message"]
