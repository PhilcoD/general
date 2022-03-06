import openpyxl

from openpyxl import Workbook

import southborough_stats.play_cricket_extract as ss_pce

def test_fixture_id_extract():
    
    wb = Workbook()
    wb.active.title = "Results"
    wb.active["A1"].value = "Fixture ID"
    wb.active["A2"].value = 1
    
    expected = ["1"]
    
    got = ss_pce.fixture_id_extract(wb)
    
    assert expected == got
