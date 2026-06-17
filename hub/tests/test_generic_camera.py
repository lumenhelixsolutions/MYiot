import pytest

from plugins.generic_camera import GenericCameraDriver


@pytest.mark.asyncio
async def test_reolink_url_templates():
    config = {
        "device_id": "cam-reolink-01",
        "manufacturer": "generic_camera",
        "model": "reolink",
        "device_type": "camera",
        "ip": "192.168.1.50",
        "username": "admin",
        "password": "secret",
    }
    driver = GenericCameraDriver(config)
    stream_url = await driver.get_stream_url()
    assert stream_url == "rtsp://admin:secret@192.168.1.50:554/h264Preview_01_main"

    state = await driver.get_state()
    assert state.state["snapshot_url"].startswith("http://192.168.1.50/cgi-bin/api.cgi")
    assert "user=admin" in state.state["snapshot_url"]
    assert "password=secret" in state.state["snapshot_url"]


@pytest.mark.asyncio
async def test_set_state_toggles_power():
    config = {
        "device_id": "cam-tapo-01",
        "manufacturer": "generic_camera",
        "model": "tapo",
        "device_type": "camera",
        "ip": "192.168.1.51",
        "username": "user",
        "password": "pass",
    }
    driver = GenericCameraDriver(config)
    await driver.set_state({"power": False})
    state = await driver.get_state()
    assert state.state["power"] is False

    await driver.set_state({"power": True})
    state = await driver.get_state()
    assert state.state["power"] is True


@pytest.mark.asyncio
async def test_custom_stream_url_takes_precedence():
    config = {
        "device_id": "cam-custom-01",
        "manufacturer": "generic_camera",
        "model": "generic_onvif",
        "device_type": "camera",
        "ip": "192.168.1.52",
        "stream_url": "rtsp://custom/url",
        "snapshot_url": "http://custom/snap",
    }
    driver = GenericCameraDriver(config)
    assert await driver.get_stream_url() == "rtsp://custom/url"
    state = await driver.get_state()
    assert state.state["snapshot_url"] == "http://custom/snap"
