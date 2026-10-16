from datetime import date
from math import isclose
import unittest

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from stockfollower.gui import _draw_signal_markers
from stockfollower.signals import Signal, detect_kdj_signals


def test_detector_crossings_equality_and_missing_data():
    dates = [date(2026, 10, day) for day in range(1, 12)]
    k = [None, 40, 50, 40, 50, 60, 50, 40, None, 60, 40]
    signals = detect_kdj_signals(dates, k, [50] * len(dates))
    assert signals == [
        Signal(dates[5], "golden_cross"),
        Signal(dates[7], "death_cross"),
        Signal(dates[10], "death_cross"),
    ]


def test_detector_requires_matching_dates():
    with unittest.TestCase().assertRaises(ValueError):
        detect_kdj_signals([], [50], [50])


def test_markers_align_with_candles_through_pan_zoom_and_range_change():
    # Non-trading days do not occupy x positions.
    dates = [date(2026, 10, day) for day in (2, 5, 6)]
    signals = [Signal(dates[1], "golden_cross"), Signal(dates[2], "death_cross"),
               Signal(date(2026, 9, 30), "golden_cross")]
    figure = Figure()
    canvas = FigureCanvasAgg(figure)
    axis = figure.add_subplot()
    axis.bar([0, 1, 2], [10, 11, 12])
    _draw_signal_markers(axis, dates, signals)
    assert [text.get_text() for text in axis.texts] == ["G", "D"]
    assert axis.texts[0].get_color() != axis.texts[1].get_color()
    assert axis.lines[0].get_linestyle() != axis.lines[1].get_linestyle()
    for limits in [(-0.5, 2.5), (0.5, 1.5), (1.5, 2.5)]:
        axis.set_xlim(*limits)
        axis.set_ylim(5, 20)
        canvas.draw()
        for position, line, text in zip((1, 2), axis.lines, axis.texts):
            candle_x = axis.transData.transform((position, 10))[0]
            assert isclose(line.get_transform().transform((position, 0))[0], candle_x)
            assert isclose(text.get_transform().transform(text.get_position())[0], candle_x)
            assert text.get_clip_on()
    axis.clear()
    _draw_signal_markers(axis, dates[1:], signals)
    assert [list(line.get_xdata()) for line in axis.lines] == [[0, 0], [1, 1]]


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(unittest.FunctionTestCase(test) for test in (
        test_detector_crossings_equality_and_missing_data,
        test_detector_requires_matching_dates,
        test_markers_align_with_candles_through_pan_zoom_and_range_change,
    ))
