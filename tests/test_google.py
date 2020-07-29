# SPDX-FileCopyrightText: © 2020 Matt Williams <matt@milliams.com>
# SPDX-License-Identifier: MIT

import googleapiclient.discovery  # type: ignore
import googleapiclient.errors  # type: ignore
import pytest  # type: ignore

from mebula.google import mock_google, extract_path_parameters


def test_google_empty():
    with mock_google():
        compute = googleapiclient.discovery.build("compute", "v1")
        assert compute.instances().list(project="foo", zone="bar").execute() == {}


def test_google_get_missing():
    with mock_google():
        compute = googleapiclient.discovery.build("compute", "v1")
        with pytest.raises(googleapiclient.errors.HttpError) as e:
            compute.instances().get(project="p", zone="z", instance="none").execute()
        assert e.value.resp.status == "404"


def test_google_one_round_trip():
    with mock_google():
        compute = googleapiclient.discovery.build("compute", "v1")
        compute.instances().insert(
            project="foo", zone="bar", body={"name": "foo", "tags": {}}
        ).execute()
        instances = compute.instances().list(project="foo", zone="bar").execute()
        assert "items" in instances
        assert len(instances["items"]) == 1
        assert instances["items"][0]["name"] == "foo"

        i = compute.instances().get(project="foo", zone="bar", instance="foo").execute()
        assert instances["items"][0] == i


def test_google_list_filter():
    with mock_google():
        compute = googleapiclient.discovery.build("compute", "v1")
        collection = compute.instances()
        collection.insert(project="p", zone="z", body={"name": "foo1"}).execute()
        collection.insert(project="p", zone="z", body={"name": "foo2"}).execute()
        instances = collection.list(project="p", zone="z", filter="name=foo2").execute()
        assert len(instances["items"]) == 1
        assert instances["items"][0]["name"] == "foo2"


def test_extract_path_parameters():
    path = "/compute/v1/projects/prfoo/zones/zbar/instances"
    template = "/compute/v1/projects/{project}/zones/{zone}/instances"

    expected = {"project": "prfoo", "zone": "zbar"}

    assert extract_path_parameters(path, template) == expected


def test_list_machine_types():
    with mock_google():
        compute = googleapiclient.discovery.build("compute", "v1")
        types = (
            compute.machineTypes().list(project="foo", zone="bar").execute()["items"]
        )
        assert len(types) > 0
        assert "imageSpaceGb" in types[0]
        assert isinstance(types[0]["imageSpaceGb"], int)


def test_filter_machine_types():
    with mock_google():
        compute = googleapiclient.discovery.build("compute", "v1")
        types = (
            compute.machineTypes()
            .list(project="foo", zone="bar", filter="name='n1-standard-1'")
            .execute()["items"]
        )
        assert len(types) == 1
        assert "name" in types[0]
        assert types[0]["name"] == "n1-standard-1"


def test_get_machine_types():
    with mock_google():
        compute = googleapiclient.discovery.build("compute", "v1")
        machine_type = (
            compute.machineTypes()
            .get(project="foo", zone="bar", machineType="n1-standard-1")
            .execute()
        )
        assert "name" in machine_type
        assert machine_type["name"] == "n1-standard-1"
