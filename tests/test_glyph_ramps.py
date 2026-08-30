"""The capacity-to-glyph ladders in the bar. Both had duplicate branches once."""

import pytest
from widgets.bluetooth import WidgetBluetooth
from widgets.power_supply import WidgetPowerSupply


@pytest.fixture
def bluetooth() -> WidgetBluetooth:
    return WidgetBluetooth(r=None)


@pytest.fixture
def power() -> WidgetPowerSupply:
    return WidgetPowerSupply(r=None)


# The scale used integer division, so round() below it never did anything: the full block
# appeared only at exactly 100 and everything from 86 up collapsed into one level.
def test_bluetooth_capacity_uses_the_whole_ladder(bluetooth: WidgetBluetooth) -> None:
    reached = {bluetooth._level_index(capacity) for capacity in range(101)}
    assert reached == set(range(len(bluetooth.CAPACITY_SYMBOLS)))


def test_bluetooth_capacity_is_monotonic(bluetooth: WidgetBluetooth) -> None:
    indices = [bluetooth._level_index(capacity) for capacity in range(101)]
    assert indices == sorted(indices)


@pytest.mark.parametrize(("capacity", "index"), [(0, 0), (100, 7)])
def test_bluetooth_capacity_endpoints(bluetooth: WidgetBluetooth, capacity: int, index: int) -> None:
    assert bluetooth._level_index(capacity) == index


@pytest.mark.parametrize("capacity", [-50, -1, 101, 1000])
def test_bluetooth_capacity_clamps(bluetooth: WidgetBluetooth, capacity: int) -> None:
    assert 0 <= bluetooth._level_index(capacity) < len(bluetooth.CAPACITY_SYMBOLS)


# Both ladders once had duplicate *branches*: charging mapped 50 % and 30 % to one glyph and
# 40 % and 20 % to another, so the ramp went backwards and some glyphs were unreachable. A
# glyph repeating in adjacent buckets is fine -- Material Design has no battery-0, so 0-9 %
# and 10-19 % share the empty outline -- but a repeat with a different glyph between them
# means the ladder is out of order.
@pytest.mark.parametrize("charging", [True, False])
def test_battery_glyphs_never_repeat_out_of_order(power: WidgetPowerSupply, charging: bool) -> None:
    ramp = power.CHARGING_SYMBOLS if charging else power.DISCHARGING_SYMBOLS
    for glyph in set(ramp):
        positions = [i for i, g in enumerate(ramp) if g == glyph]
        assert positions == list(range(positions[0], positions[-1] + 1)), (
            f"{glyph!r} appears at {positions} with another glyph between them"
        )


@pytest.mark.parametrize("charging", [True, False])
def test_every_bucket_draws_something_from_its_own_ramp(power: WidgetPowerSupply, charging: bool) -> None:
    ramp = power.CHARGING_SYMBOLS if charging else power.DISCHARGING_SYMBOLS
    for capacity in range(101):
        drawn = power._symbol(capacity, charging)
        glyph = drawn.split(">")[-2].split("<")[0] if drawn.startswith("<span") else drawn
        assert glyph in ramp, f"{capacity}% drew something outside the ramp"


@pytest.mark.parametrize("capacity", [-10, 0, 100, 250])
def test_battery_capacity_clamps(power: WidgetPowerSupply, capacity: int) -> None:
    assert power._symbol(capacity, charging=True) in power.CHARGING_SYMBOLS


def test_a_low_battery_is_marked_only_while_discharging(power: WidgetPowerSupply) -> None:
    assert power._symbol(5, charging=False).startswith("<span color=")
    assert not power._symbol(5, charging=True).startswith("<span")
    assert not power._symbol(95, charging=False).startswith("<span")
