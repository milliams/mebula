# SPDX-FileCopyrightText: © 2020 Matt Williams <matt@milliams.com>
# SPDX-License-Identifier: MIT

import pytest
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient  # type: ignore

from mebula.azure import mock_azure


@pytest.fixture
def compute_client():
    with mock_azure():
        credential = DefaultAzureCredential()
        yield ComputeManagementClient(
            credential=credential,
            subscription_id="foo",
        )


def test_azure_empty(compute_client):
    assert list(compute_client.virtual_machines.list("group")) == []


def test_mock_azure(compute_client):
    c = {
        "location": "eastus",
        "os_profile": {
            "computer_name": "instance-1",
            "admin_username": "myusername",
            "admin_password": "mypassword",
        },
        "hardware_profile": {"vm_size": "Standard_DS1_v2"},
        "storage_profile": {
            "image_reference": {
                "publisher": "Canonical",
                "offer": "UbuntuServer",
                "sku": "16.04.0-LTS",
                "version": "latest",
            },
        },
    }

    a = compute_client.virtual_machines.create_or_update("group", "ins", c).result()
    b = compute_client.virtual_machines.get("group", "ins").result()
    assert a == b
    c = list(compute_client.virtual_machines.list("group"))[0]
    assert b == c
