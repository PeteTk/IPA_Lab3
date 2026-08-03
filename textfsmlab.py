from netmiko import ConnectHandler

# 1. ฟังก์ชันสำหรับสร้าง Description (เขียนไว้ด้านบนสุดเพื่อให้ test_textfsm.py เรียกใช้ได้)
def generate_description(port=None, device=None, is_pc=False, is_wan=False):
    if is_pc:
        return "Connect to PC"
    if is_wan:
        return "Connect to WAN"
    return f"Connect to {port} of {device}"

# 2. ป้องกันไม่ให้โค้ดทำงานอัตโนมัติเวลาโดนสั่งรันจาก pytest
if __name__ == "__main__":
    
    # ประกาศข้อมูลอุปกรณ์ (สามารถแก้ username/password ให้ตรงกับที่ตั้งไว้ใน Lab)
    r1 = {
        "name": "R1",
        "device_type": "cisco_ios",
        "host": "172.31.111.4",
        "username": "admin",
        "use_keys": True
    }
    r2 = {
        "name": "R2",
        "device_type": "cisco_ios",
        "host": "172.31.111.5",
        "username": "admin",
        "use_keys": True
    }
    s1 = {
        "name": "S1",
        "device_type": "cisco_ios",
        "host": "172.31.111.3",
        "username": "admin",
        "use_keys": True

    }

    devices = [r1, r2, s1]

    # 3. เริ่มวนลูปทำงานทีละเครื่อง
    for device in devices:
        # ดึงชื่อออกมาเพื่อใช้แสดงผลและเป็นเงื่อนไขเช็ค
        device_name = device.pop("name")
        print(f"\n[+] Connecting to {device_name}...")
        
        try:
            # เชื่อมต่อและเข้าโหมด enable
            net_connect = ConnectHandler(**device)
            net_connect.enable()
            
            # ส่งคำสั่งและดึงข้อมูลมาเป็นแบบ List of Dictionaries
            cdp_data = net_connect.send_command("show cdp neighbors", use_textfsm=True)
            config_commands = []
            
            # 4. แปลงข้อมูล CDP ไปเป็นคำสั่ง Description
            if isinstance(cdp_data, list):
                for item in cdp_data:
                    # ใช้ชื่อ Key ที่ตรงกับ cisco_ios_show_cdp_neighbors.textfsm
                    local_port = item['local_interface']
                    remote_device = item['neighbor_name']
                    remote_port = item['neighbor_interface']
                    
                    # สร้าง Description สำหรับพอร์ตที่ต่อกับ Router/Switch ด้วยกัน
                    desc = generate_description(port=remote_port, device=remote_device)
                    config_commands.extend([f"interface {local_port}", f"description {desc}"])
            
            # 5. ใส่เงื่อนไขพิเศษตาม Topology
            # เป็นสาย WAN สำหรับ R2 G0/3
            if device_name == "R2":
                desc_wan = generate_description(is_wan=True)
                config_commands.extend(["interface GigabitEthernet0/3", f"description {desc_wan}"])
                
            # เป็นสาย PC สำหรับ R1 G0/1 และ S1 G0/1
            if device_name in ["R1", "S1"]:
                desc_pc = generate_description(is_pc=True)
                config_commands.extend(["interface GigabitEthernet0/1", f"description {desc_pc}"])
                
            # 6. ส่งชุดคำสั่งทั้งหมดเข้าอุปกรณ์
            if config_commands:
                print(f"[*] Sending configurations to {device_name}...")
                
                # --- เพิ่ม 2 บรรทัดนี้เพื่อให้มันโชว์คำสั่งบนหน้าจอ ---
                for cmd in config_commands:
                    print(f"    -> {cmd}")
                # ----------------------------------------
                
                net_connect.send_config_set(config_commands)
                print("Configured successfully!")
                
            net_connect.disconnect()
            
        except Exception as e:
            print(f"[!] Error on {device_name}: {e}")