# Changelog

## 0.13.0 (unreleased)

### Added
- Prana Neo support: `PranaDeviceInfo.model_id` and `is_neo`, the
  `PranaState.fresh_air_position` and `extract_position` fields, and the
  `PranaPositionType` enum with `PranaLocalApiClient.set_position()`
  (`POST /setPosition`).
- `PranaLocalApiClient` accepts an external `aiohttp.ClientSession` (`session=`)
  and a `timeout=`, and has a `close()` method.
- `PranaApiInvalidResponse` for payloads that are not a JSON object.
- Device simulator: the `prana-simulator` command, or
  `python -m prana_local_api_client.simulator`.
- Top-level exports (`from prana_local_api_client import PranaLocalApiClient`),
  plus a `py.typed` marker.

### Fixed
- `get_state()` no longer wraps network and HTTP errors in a plain
  `UpdateFailed`. It now raises `PranaApiCommunicationError` or
  `PranaApiUpdateFailed`, which is what callers (such as Home Assistant) catch.
  All request errors still inherit from `UpdateFailed`, so existing
  `except UpdateFailed` code keeps working.
- Enums format as their value (`f"{PranaFanType.SUPPLY}"` gives `"supply"`).
- Responses without a JSON content type are parsed. Malformed sensor values
  become `None` instead of raising.
- Failed requests are no longer logged as errors by the library; they are
  raised to the caller.

### Changed
- `set_speed`, `set_speed_is_on`, `set_switch` and `set_position` validate
  their type argument and raise `ValueError` for unknown values.
- CI: lint, strict mypy and tests on Python 3.10–3.14, `pip-audit`, and a test
  build. The release workflow now checks that the tag matches the package
  version.

## 0.12.0
- Night and boost fields in `PranaState`.
