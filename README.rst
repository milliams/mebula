******
Mebula
******

Mebula is a framework which you can use in your testing code to mock your calls to cloud providers' APIs.
At the moment, Oracle's OCI, Google Cloud and Microsoft Azure are supported.

Installation
============

- For Microsoft Azure, install the ``mebula[azure]`` package.
- For Google Cloud, install the ``mebula[google]`` package.
- For Oracle's OCI, install the ``mebula[oracle]`` package.

Usage
=====

Azure
-----

You can use the ``mock_azure`` context manager and then use the Azure functions as normal:

.. code:: python

    from azure.common.client_factory import get_client_from_json_dict
    from azure.mgmt.compute import ComputeManagementClient

    from mebula.azure import mock_azure


    def test_azure():
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
            client = get_client_from_json_dict(ComputeManagementClient, config_dict)

            assert list(client.virtual_machines.list("group")) == []

Google
------

You can use the ``mock_google`` context manager and then use the Google API functions as normal:

.. code:: python

    import googleapiclient.discovery

    from mebula import mock_google


    def test_google(client):
        with mock_google():
            client = googleapiclient.discovery.build("compute", "v1")

            assert client.instances().list(project="foo", zone="bar").execute() == {}

Oracle
------

You can use the ``mock_oracle`` context manager and then use the Oracle ``oci`` functions as normal:

.. code:: python

    import oci

    from mebula.oracle import mock_oracle


    def test_oracle():
        with mock_oracle():
            compute = oci.core.ComputeClient(config={})

            assert compute.list_instances("foo").data == []

Coverage
========

Coverage is very minimal at the moment. Only launching and listing instances is supported.
