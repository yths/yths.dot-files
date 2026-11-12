"""The capacity-to-symbol ladders in the bar. Both had duplicate branches once.

Every test here runs twice: once against the ASCII vocabulary a bundle that overrides nothing
gets, and once against the ladders the shipped bundle actually installs. The properties are
what matter rather than the characters -- a ramp has to be monotonic, has to cover its whole
range, and has to be long enough for the index its widget computes -- and they have to hold
for a theme's ladder as much as for the fallback, because a theme supplies its own and
nothing else checks it.
"""

import json
import pathlib

import pytest
import symbols
from widgets.bluetooth import WidgetBluetooth
from widgets.power_supply import WidgetPowerSupply

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _vocabularies() -> list[pytest.param]:
    bundle = json.loads((REPO_ROOT / "assets/default/config.json").read_text())
    ascii_only, _ = symbols.resolve({})
    shipped, _ = symbols.resolve(bundle)
    return [pytest.param(ascii_only, id="ascii"), pytest.param(shipped, id="bundle")]


@pytest.fixture(params=_vocabularies())
def vocabulary(request: pytest.FixtureRequest) -> dict:
    return request.param


@pytest.fixture
def bluetooth(vocabulary: dict) -> WidgetBluetooth:
    return WidgetBluetooth(r=None, symbols=vocabulary)


@pytest.fixture
def power(vocabulary: dict) -> WidgetPowerSupply:
    return WidgetPowerSupply(r=None, symbols=vocabulary)


# The scale used integer division, so round() below it never did anything: the full block
# appeared only at exactly 100 and everything from 86 up collapsed into one level.
def test_bluetooth_capacity_uses_the_whole_ladder(bluetooth: WidgetBluetooth) -> None:
    reached = {bluetooth._level_index(capacity) for capacity in range(101)}
    assert reached == set(range(len(bluetooth.symbols["meter.ramp"])))


def test_bluetooth_capacity_is_monotonic(bluetooth: WidgetBluetooth) -> None:
    indices = [bluetooth._level_index(capacity) for capacity in range(101)]
    assert indices == sorted(indices)


@pytest.mark.parametrize(("capacity", "index"), [(0, 0), (100, 7)])
def test_bluetooth_capacity_endpoints(
    bluetooth: WidgetBluetooth, capacity: int, index: int
) -> None:
    assert bluetooth._level_index(capacity) == index


@pytest.mark.parametrize("capacity", [-50, -1, 101, 1000])
def test_bluetooth_capacity_clamps(bluetooth: WidgetBluetooth, capacity: int) -> None:
    assert 0 <= bluetooth._level_index(capacity) < len(bluetooth.symbols["meter.ramp"])


# Both ladders once had duplicate *branches*: charging mapped 50 % and 30 % to one symbol and
# 40 % and 20 % to another, so the ramp went backwards and some symbols were unreachable. A
# symbol repeating in adjacent buckets is fine -- Material Design has no battery-0, so 0-9 %
# and 10-19 % share the empty outline -- but a repeat with a different symbol between them
# means the ladder is out of order.
@pytest.mark.parametrize("charging", [True, False])
def test_battery_symbols_never_repeat_out_of_order(
    power: WidgetPowerSupply, charging: bool
) -> None:
    ramp = power.symbols["battery.charging" if charging else "battery.discharging"]
    for symbol in set(ramp):
        positions = [i for i, s in enumerate(ramp) if s == symbol]
        assert positions == list(range(positions[0], positions[-1] + 1)), (
            f"{symbol!r} appears at {positions} with another symbol between them"
        )


@pytest.mark.parametrize("charging", [True, False])
def test_every_bucket_draws_something_from_its_own_ramp(
    power: WidgetPowerSupply, charging: bool
) -> None:
    ramp = power.symbols["battery.charging" if charging else "battery.discharging"]
    for capacity in range(101):
        drawn = power._symbol(capacity, charging)
        symbol = drawn.split(">")[-2].split("<")[0] if drawn.startswith("<span") else drawn
        assert symbol in ramp, f"{capacity}% drew something outside the ramp"


@pytest.mark.parametrize("capacity", [-10, 0, 100, 250])
def test_battery_capacity_clamps(power: WidgetPowerSupply, capacity: int) -> None:
    assert power._symbol(capacity, charging=True) in power.symbols["battery.charging"]


def test_a_low_battery_is_marked_only_while_discharging(power: WidgetPowerSupply) -> None:
    assert power._symbol(5, charging=False).startswith("<span color=")
    assert not power._symbol(5, charging=True).startswith("<span")
    assert not power._symbol(95, charging=False).startswith("<span")


# A ramp one rung short is an IndexError inside poll(), which stops qtile rescheduling that
# cell for the rest of the session. The widgets index by `capacity // 10` and by the meter's
# own step count, so the length is a contract rather than a detail.
def test_every_ramp_is_long_enough_for_the_index_its_widget_computes(
    vocabulary: dict,
) -> None:
    assert symbols.malformed(vocabulary) == []
