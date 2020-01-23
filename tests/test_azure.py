import pytest  # type: ignore
from azure.common.client_factory import get_client_from_json_dict  # type: ignore
from azure.mgmt.compute import ComputeManagementClient  # type: ignore

from mebula.azure import mock_azure


@pytest.fixture
def compute_client():
    with mock_azure():
        config_dict = {
            "clientId": "ad735158-65ca-11e7-ba4d-ecb1d756380e",
            "clientSecret": "b70bb224-65ca-11e7-810c-ecb1d756380e",
            "subscriptionId": "bfc42d3a-65ca-11e7-95cf-ecb1d756380e",
            "tenantId": "c81da1d8-65ca-11e7-b1d1-ecb1d756380e",
            "activeDirectoryEndpointUrl": "https://login.microsoftonline.com",
            "resourceManagerEndpointUrl": "https://management.azure.com/",
            "activeDirectoryGraphResourceId": "https://graph.windows.net/",
            "sqlManagementEndpointUrl": "https://management.core.windows.net:8443/",
            "galleryEndpointUrl": "https://gallery.azure.com/",
            "managementEndpointUrl": "https://management.core.windows.net/",
        }
        yield get_client_from_json_dict(ComputeManagementClient, config_dict)


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
