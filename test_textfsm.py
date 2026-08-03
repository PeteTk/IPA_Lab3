# test_textfsm.py
from textfsmlab import generate_description

def test_cdp_description():
    # ทดสอบ Format ปกติที่ได้จาก CDP
    assert generate_description("G0/1", "R2") == "Connect to G0/1 of R2"

def test_pc_description():
    # ทดสอบ Format สำหรับ PC
    assert generate_description(is_pc=True) == "Connect to PC"

def test_wan_description():
    # ทดสอบ Format สำหรับ WAN
    assert generate_description(is_wan=True) == "Connect to WAN"