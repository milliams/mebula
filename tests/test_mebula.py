from mebula import mock_azure, mock_google, mock_oracle


def test_mock_azure():
    with mock_azure():
        pass


def test_mock_google():
    with mock_google():
        pass


def test_mock_oracle():
    with mock_oracle():
        pass
