import time
import can
import threading

SF = 0          # single frame
FF = 1          # first frame
CF = 2          # consecutive frame
FC = 3          # flow control        

CTS = 0         # Clear to send
WAIT = 1        # wait
OVFLW = 2         # overflow

DUM_BYTE = 0x00
ID_SEND = 0x089
ID_RECEIVE = 0x99

class Receive_State():
    def __init__(self) -> None:
        self.SF = 0
        self.FF = 0
        self.CF = 0
        self.send_FC = 0
        self.done = 0
        self.time_Ar = 0
        self.time_Br = 0
        self.time_Cr = 0

class Info():
    def __init__(self) -> None:
        self.SN_cnt = 0
        self.BS_cnt = 0
        self.data_hex_buf = []
        self.data_str_buffer = ""
        self.RX_DL = 0
        self.data_length = 0
        self.STmin = 0
    def reset_param(self):
        self.SN_cnt = 0
        self.BS_cnt = 0
        self.data_hex_buf = []
        self.data_str_buffer = ""
        self.RX_DL = 0
        self.data_length = 0

class RvcTimeout():
    def __init__(self, Ar:int, Br: int, Cr: int) -> None:
        self.Ar = Ar
        self.Br = Br
        self.Cr = Cr

class TsmTimeout():
    def __init__(self, As:int, Bs: int, Cs: int) -> None:
        self.As = As
        self.Bs = Bs
        self.Cs = Cs
        
class Frame():
    framefomart: list
    def __init__(self, frametype: int, length: int, data: list = None, **kwargs) -> None:
        self.framefomart = list([DUM_BYTE] * length)
        DL = kwargs.get('DL', None)
        SN = kwargs.get('SN', None)
        FS = kwargs.get('FS', None)
        BS = kwargs.get('BS', None)
        STmin = kwargs.get('STmin', None)
        if frametype == SF:                     # need frametype, data, len
            if length <= 8:
                self.framefomart[0] = (SF << 4) | (length - 1)
                self.framefomart[1:len(data) + 1] = data
            elif length == 12 or length == 16 or length == 20 or length == 24 or length == 32 or length == 48 or length == 64:
                self.framefomart[0] = SF
                self.framefomart[1] = length - 2
                self.framefomart[2:len(data) + 2] = data
            else: 
                print("Invalid param")  
        elif frametype == FF:                   # need frametype, data, len, DL
            if DL <= 4095:
                self.framefomart[0] = (FF << 4) | (DL >> 8)
                self.framefomart[1] = DL & 0xFF
                replace_elements(self.framefomart, data, 2)             #remove 0 at the end of frame
            else:
                self.framefomart[0] = (FF << 4)
                self.framefomart[1] = 0
                self.framefomart[2:6] = list(DL.to_bytes(4, byteorder='big'))
                replace_elements(self.framefomart, data, 6)
        elif frametype == CF:                    # need frametype, data, len, SN
            self.framefomart[0] = (CF << 4) | SN
            self.framefomart[1:len(data) + 1] = data
        elif frametype == FC:                    # need frametype, data, len, BS, STmin
            self.framefomart[0] = (FC << 4) | FS
            self.framefomart[1] = BS
            self.framefomart[2] = STmin
        else:
            print("Invalid param")

def SingleFrameHandle(msg: can.Message, bus: int):
    global Receive_State_Info, Receive_Info
    if msg.dlc <= 8: 
        if msg.data[0] & 0x0F == msg.dlc - 1:
            print(f"Bus {bus} Receive SF {ascii_list_to_string(list(msg.data), DUM_BYTE, 1)}")
            Receive_Info.data_str_buffer = ascii_list_to_string(list(msg.data), DUM_BYTE, 1)
            Receive_State_Info.SF = 1
        else:
            print("Bus {bus} Receive Error")
    elif msg.dlc == 12 or msg.dlc == 16 or msg.dlc == 20 or msg.dlc == 24 or msg.dlc == 32 or msg.dlc == 48 or msg.dlc == 64:
        if msg.data[0] & 0x0F == 0 and msg.data[1] == msg.dlc - 2:
            print(f"Bus {bus} Receive SF {ascii_list_to_string(list(msg.data), DUM_BYTE, 2)}")
            Receive_Info.data_str_buffer = ascii_list_to_string(list(msg.data), DUM_BYTE, 1)
            Receive_State_Info.SF = 1
        else:
            print(f"Bus {bus} Receive Error")
    else: 
        print(f"Bus {bus} Receive SF Fail")

def FirstFrameHandle(msg: can.Message, bus: int):
    global Receive_Info, BS, STmin, Receive_State_Info
    if (msg.data[0] & 0x0F) << 8 | msg.data[1] != 0:
        Receive_Info.data_length = (msg.data[0] & 0x0F) << 8 | msg.data[1]
        Receive_State_Info.time_Ar = time.time()
        if Receive_Info.data_length != 0:
            Receive_Info.BS_cnt = 2
            Receive_Info.SN_cnt = 0
            Receive_Info.RX_DL = msg.dlc
            Receive_Info.data_hex_buf.clear()
            Receive_Info.data_str_buffer = ""
            Receive_Info.data_hex_buf.extend(msg.data[2:])
            Receive_Info.data_str_buffer += ascii_list_to_string(Receive_Info.data_hex_buf, DUM_BYTE)
            print(f"Bus {bus} Receive FF {Receive_Info.data_str_buffer}")
            Receive_State_Info.FF = 1

            # check available buffer

            FC_frame = Frame(frametype=FC, length=8, FS = CTS, BS = BS, STmin = STmin) 
            msg_send_fc = can.Message(arbitration_id=0xAA, data=FC_frame.framefomart, is_extended_id=False)
            if bus == 1:
                bus1.send(msg_send_fc)
            else:
                bus2.send(msg_send_fc)
        else:
            print(f"Bus {bus} Bus {bus} Receive FF 1fail")
    else:
        Receive_Info.data_length = (msg.data[2] << 24) | (msg.data[3] << 16) | (msg.data[4] << 8) | msg.data[5]
        if Receive_Info.data_length != 0:
            Receive_Info.BS_cnt = 2
            Receive_Info.SN_cnt = 0
            Receive_Info.RX_DL = msg.dlc
            Receive_Info.data_hex_buf.clear()
            Receive_Info.data_str_buffer = ""
            Receive_Info.data_hex_buf.extend(msg.data[6:])
            Receive_Info.data_str_buffer += ascii_list_to_string(Receive_Info.data_hex_buf, DUM_BYTE)
            print(f"Bus {bus} Receive FF {Receive_Info.data_str_buffer}")
            Receive_State_Info.FF = 1

            # check available buffer
            FC_frame = Frame(frametype=FC, length=8, FS = CTS, BS = BS, STmin = STmin) 
            msg_send_fc = can.Message(arbitration_id=0xAA, data=FC_frame.framefomart, is_extended_id=False)
            if bus == 1:
                bus1.send(msg_send_fc)
            else:
                bus2.send(msg_send_fc)
        else:
            print(f"Bus {bus} Receive FF 2fail")

def ConsecutiveFrameHandle(msg: can.Message, bus: int):
    global Receive_Info
    if msg.dlc == 8 or msg.dlc == 12 or msg.dlc == 16 or msg.dlc == 20 or msg.dlc == 24 or msg.dlc == 32 or msg.dlc == 48 or msg.dlc == 64:
        if msg.dlc == Receive_Info.RX_DL and ((msg.data[0] & 0x0F == Receive_Info.SN_cnt + 1) or (msg.data[0] & 0x0F == 0 and Receive_Info.SN_cnt == 15)):
            Receive_Info.SN_cnt = msg.data[0] & 0x0F
            Receive_Info.data_hex_buf.clear()
            Receive_Info.data_hex_buf.extend(msg.data[1:])
            Receive_Info.BS_cnt -= 1
            Receive_Info.data_str_buffer += ascii_list_to_string(Receive_Info.data_hex_buf, DUM_BYTE)
            Receive_State_Info.CF = 1
            print(f"Bus {bus} Receive CS {Receive_Info.SN_cnt}: {Receive_Info.data_str_buffer}")
            if len(Receive_Info.data_str_buffer) < Receive_Info.data_length:
                if Receive_Info.BS_cnt == 0:
                    Receive_Info.BS_cnt = 2
                    FC_frame = Frame(frametype=FC, length=8, FS = CTS, BS = 2, STmin = STmin)           # 127 ms
                    msg_send_fc = can.Message(arbitration_id=0xAA, data=FC_frame.framefomart, is_extended_id=False)
                    if bus == 1:
                        bus1.send(msg_send_fc)
                    else:
                        bus2.send(msg_send_fc)
            else:
                print("Complete receive")
        else:
            print(f"Bus {bus} Receive CS fail1 {msg.data[0]}, {Receive_Info.SN_cnt + 1} {(msg.data[0] & 0x0F == Receive_Info.SN_cnt + 1)} {msg.data[0] == 0 and Receive_Info.SN_cnt == 15}")
    else:
        print(f"Bus {bus} Receive CS fail3")

def FlowControlHandle(msg: can.Message, bus: int):
    global Transmit_Info, receive_fc
    # global BS, receive_fc, BS_cnt
    if msg.dlc == 8:
        if msg.data[0] & 0x0F == CTS:
            receive_fc = 1
            Transmit_Info.BS_cnt = msg.data[1]
            Transmit_Info.STmin = msg.data[2]
            print(f"Bus {bus} Receive CTS ")
        elif msg.data[0] &0x0F == WAIT:
            print(f"Bus {bus} Receive WAIT")
            # reload Bs
        elif msg.data[0] &0x0F == OVFLW:  
            print(f"Bus {bus} Overflow, abort connection")
    else: 
        print(f"Bus {bus} Receive FC fail, abort connection")

def string_to_ascii_list(str):
    return [ord(char) for char in str]

def ascii_list_to_string(ascii_list, dummy_byte, start_index=0):
    return ''.join(chr(byte) for byte in ascii_list[start_index:] if byte != dummy_byte)

def replace_elements(list1, list2, n):
    num_elements_to_replace = min(len(list1) - n, len(list2))
    list1[n:n + num_elements_to_replace] = list2[:num_elements_to_replace]
    return list1

def CalculateSTmin(Stmin: int = 0):
    if STmin <= 127: 
        return STmin / 1000
    elif Stmin >= 0xF1 and Stmin <= 0xF9:
        return (STmin & 0x0F) / 10000

class ListenerHandlebus2(can.Listener):
    def on_message_received(self, msg: can.Message):
        print(f"Receive message bus 2: {msg}")
        if msg.data[0] >> 4 == 0:
            print("Single frame")
            SingleFrameHandle(msg, 2)
        elif msg.data[0] >> 4 == 1:
            print("First frame")
            FirstFrameHandle(msg, 2)
        elif msg.data[0] >> 4 == 2:
            print("Consecutive frame")
            ConsecutiveFrameHandle(msg, 2)
        elif msg.data[0] >> 4 == 3:
            print("Flow control")
            FlowControlHandle(msg, 2)

class ListenerHandlebus1(can.Listener):
    def on_message_received(self, msg: can.Message):
        print(f"Receive message bus 1: {msg}")
        if msg.data[0] >> 4 == 0:
            print("Single frame")
            SingleFrameHandle(msg, 1)
        elif msg.data[0] >> 4 == 1:
            print("First frame")
            FirstFrameHandle(msg, 1)
        elif msg.data[0] >> 4 == 2:
            print("Consecutive frame")
            ConsecutiveFrameHandle(msg, 1)
        elif msg.data[0] >> 4 == 3:
            print("Flow control")
            FlowControlHandle(msg, 1)

def Transmit(bus: int, id: int, TX_DL: int , data_buf: list, length: int, is_fd: bool = False):
    global Transmit_Info, bus1, bus2, receive_fc
    index = last_index = 0           #begin index of new frame in buffer
    
    if (length < 7 and TX_DL == 8):                         #single frame <= 8
        send_frame = Frame(frametype=SF, length=TX_DL, data=data_buf)
        msg_send = can.Message(arbitration_id=id, data=send_frame.framefomart, is_fd=is_fd)
        if bus == 1:
            bus1.send(msg_send)
        elif bus == 2:
            bus2.send(msg_send)
    elif (length < TX_DL - 2 and ( TX_DL == 12 or TX_DL == 16 or TX_DL == 20 or TX_DL == 24 or TX_DL == 32 or TX_DL == 48 or TX_DL == 64)):         #SF > 8
        send_frame = Frame(frametype=SF, length=TX_DL, data=data_buf)
        msg_send = can.Message(arbitration_id=id, data=send_frame.framefomart, is_fd=True)
        if bus == 1:
            bus1.send(msg_send)
        elif bus == 2:
            bus2.send(msg_send)
    elif length <= 4095:
        receive_fc = 0
        # bs_cnt = BS
        index = TX_DL - 2
        send_frame = Frame(frametype=FF, length=TX_DL, data=data_buf[:index], DL=length)
        msg_send = can.Message(arbitration_id=id, data=send_frame.framefomart, is_fd=True)
        Transmit_Info.SN_cnt += 1
        if bus == 1:
            bus1.send(msg_send)
        elif bus == 2:
            bus2.send(msg_send)
        while receive_fc == 0:
            pass
        while index < length - 1:
            done = 0
            time.sleep(CalculateSTmin(Transmit_Info.STmin))
            receive_fc = 0
            bs_cnt = BS
            if index + TX_DL - 1 < length - 1:              # check
                last_index = index
                index = index + TX_DL - 1
                send_frame = Frame(frametype=CF, length=TX_DL, data=data_buf[last_index:index], SN=Transmit_Info.SN_cnt)
                Transmit_Info.SN_cnt += 1
                if Transmit_Info.SN_cnt == 16:
                    Transmit_Info.SN_cnt = 0
                bs_cnt -= 1 
                time.sleep(CalculateSTmin(Transmit_Info.STmin))
            else:
                send_frame = Frame(frametype=CF, length=TX_DL, data=data_buf[index:], SN=Transmit_Info.SN_cnt)
                Transmit_Info.SN_cnt += 1
                if Transmit_Info.SN_cnt == 16:
                    Transmit_Info.SN_cnt = 0
                bs_cnt -= 1
                done = 1
            msg_send = can.Message(arbitration_id=id, data=send_frame.framefomart, is_fd=True)
            if bus == 1:
                bus1.send(msg_send)
            elif bus == 2:
                bus2.send(msg_send)
            if done == 1:
                break
            while receive_fc == 0 and bs_cnt == 0:          # wait to receive FC when transmit number frame = blocksize
                pass

# def ReceiveHanle():
#     global Receive_State_Info, Receive_Info
#     Receive_Timeout = RvcTimeout(0.2, 0.2, 0.2)
#     while True:
#          while Receive_State_Info.send_FC = 1 or 
            
            

# R_thread = threading.Thread(target=ReceiveHanle)
bus1 = can.interface.Bus('test', interface='virtual')
bus2 = can.interface.Bus('test', interface='virtual')

Transmit_Info = Info()
Receive_Info = Info()

Receive_State_Info = Receive_State()

receive_fc = False

BS = 2
STmin = 50             #127 ms

mutex_send_buf = threading.Lock()
mutex_rcv_buf = threading.Lock()

if __name__ == "__main__":
    
    notifier2 = can.Notifier(bus2, [ListenerHandlebus2()])
    notifier1 = can.Notifier(bus1, [ListenerHandlebus1()])
    send_data_b ="On Sunday, the U.S. Secret Service opened fire after an agent saw a rifle barrel poking out of the bushes at Trump's golf course in West Palm Beach, a few hundred yards away from where the former president was playing. The gunman fled by car, leaving behind two backpacks and his weapon. A suspect, later identified as Ryan Routh, 58, was later arrested."
    send_data_a = "Hello"
    try:
        while 1:
            choice = input()
            if choice == 's1':
                Transmit(bus=1, id=0x012, TX_DL=8, data_buf=string_to_ascii_list(send_data_b), length=len(send_data_b))
            elif choice == 's1':
                Transmit(bus=1, id=0x012, TX_DL=8, data_buf=string_to_ascii_list(send_data_a), length=len(send_data_a))
            else:
                print("quit")
                break
    except KeyboardInterrupt:
        notifier1.stop()
        notifier2.stop()
        # shutdown bus
        bus1.shutdown()
        bus2.shutdown()