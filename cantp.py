import time
import can
import threading

def prGreen(skk): print("\033[92m {}\033[00m" .format(skk))

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

WFT = 3                 # maximum FC(WAIT) in row
BS = 2
STmin = 1             #127 ms

class Receive_State():
    def __init__(self) -> None:
        self.available_receive = 0                  # available to send , timeout will send FC(WAIT)
        self.receive_CF = 0
        self.send_FC = 0
        self.WFT_cnt = WFT
        self.is_done = 1
        self.time_Ar = 0
        self.time_Br = 0
        self.time_Cr = 0
        self.result =  0        # check timeout, 0 = in process, 1 = resul ok, 2 = result timeout 
        self.check_request = 0
    def check_Ar(self):
        self.result =  0  
        self.send_FC = 0
        self.check_request = 1
    def check_Br(self):
        self.receive_FC = 0
        self.result =  0
        self.check_request = 2
    def check_Cr(self):
        self.result =  0
        self.check_request = 3

class Transmit_State():
    def __init__(self) -> None:
        self.send_FF = 0
        self.send_CF = 0
        self.receive_FC = 0
        self.is_done = 0
        self.time_As = 0
        self.time_Bs = 0
        self.time_Cs = 0
        self.result =  0        # check timeout, 0 = in process, 1 = resul ok, 2 = result timeout 
        self.check_request = 0
    def check_As(self):
        self.result =  0
        self.send_FF = 0
        self.send_CF = 0
        self.check_request = 1
    def check_Bs(self):
        self.receive_FC = 0
        self.result =  0
        self.check_request = 2
    def check_Cs(self):
        self.result =  0
        self.check_request = 3

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

class RcvTimeout():
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
            if Receive_State_Info.is_done == 1:
                R_thread.start()
        else:
            print("Bus {bus} Receive Error")
    elif msg.dlc == 12 or msg.dlc == 16 or msg.dlc == 20 or msg.dlc == 24 or msg.dlc == 32 or msg.dlc == 48 or msg.dlc == 64:
        if msg.data[0] & 0x0F == 0 and msg.data[1] == msg.dlc - 2:
            print(f"Bus {bus} Receive SF {ascii_list_to_string(list(msg.data), DUM_BYTE, 2)}")
            Receive_Info.data_str_buffer = ascii_list_to_string(list(msg.data), DUM_BYTE, 1)
            Receive_State_Info.SF = 1
            if Receive_State_Info.is_done == 1:
                
                R_thread.start()
        else:
            print(f"Bus {bus} Receive Error")
    else: 
        print(f"Bus {bus} Receive SF Fail")

def FirstFrameHandle(msg: can.Message, bus: int):
    global Receive_Info, BS, STmin, Receive_State_Info
    if (msg.data[0] & 0x0F) << 8 | msg.data[1] != 0:
        Receive_Info.data_length = (msg.data[0] & 0x0F) << 8 | msg.data[1]
        
        if Receive_Info.data_length != 0:
            Receive_Info.BS_cnt = BS
            Receive_Info.SN_cnt = 0
            Receive_Info.RX_DL = msg.dlc
            Receive_Info.data_hex_buf.clear()
            Receive_Info.data_str_buffer = ""
            Receive_Info.data_hex_buf.extend(msg.data[2:])
            Receive_Info.data_str_buffer += ascii_list_to_string(Receive_Info.data_hex_buf, DUM_BYTE)
            print(f"Bus {bus} Receive FF {Receive_Info.data_str_buffer}")
            if Receive_State_Info.is_done == 1:
                R_thread.start()

            # check N_Br timestamp
            Receive_State_Info.check_Br()
            Receive_State_Info.time_Br = time.time()
        
            # check available buffer, add sleep here to wait or set send_FC to receive CF
            # time.sleep()
            Receive_State_Info.available_receive = 1
            if Receive_State_Info == 2:             # WFT limit reached, abort connetion
                return
            FC_frame = Frame(frametype=FC, length=8, FS = CTS, BS = BS, STmin = STmin) 
            msg_send_fc = can.Message(arbitration_id=0xAA, data=FC_frame.framefomart, is_extended_id=False)
            
            #start N_Ar
            Receive_State_Info.check_Ar()
            Receive_State_Info.time_Ar = time.time()
            if bus == 1:
                SendMsg(bus1, msg_send_fc)
            else:
                SendMsg(bus2, msg_send_fc)
            Receive_State_Info.send_FC = 1
        else:
            print(f"Bus {bus} Bus {bus} Receive FF 1fail")
    else:
        # edit later
        Receive_Info.data_length = (msg.data[2] << 24) | (msg.data[3] << 16) | (msg.data[4] << 8) | msg.data[5]
        if Receive_Info.data_length != 0:
            Receive_Info.BS_cnt = BS
            Receive_Info.SN_cnt = 0
            Receive_Info.RX_DL = msg.dlc
            Receive_Info.data_hex_buf.clear()
            Receive_Info.data_str_buffer = ""
            Receive_Info.data_hex_buf.extend(msg.data[6:])
            Receive_Info.data_str_buffer += ascii_list_to_string(Receive_Info.data_hex_buf, DUM_BYTE)
            print(f"Bus {bus} Receive FF {Receive_Info.data_str_buffer}")

            
            if Receive_State_Info.is_done == 1:
                R_thread.start()
            # check available buffer
            
            Receive_State_Info.available_receive = 1
            Receive_State_Info.time_Br = time.time()

            FC_frame = Frame(frametype=FC, length=8, FS = CTS, BS = BS, STmin = STmin) 
            msg_send_fc = can.Message(arbitration_id=0xAA, data=FC_frame.framefomart, is_extended_id=False)

            #start N_Ar
            Receive_State_Info.check_Ar()
            Receive_State_Info.time_Ar = time.time()
            if bus == 1:
                SendMsg(bus1, msg_send_fc)
            else:
                SendMsg(bus2, msg_send_fc)
            Receive_State_Info.send_FC = 1
        else:
            print(f"Bus {bus} Receive FF 2fail")

def ConsecutiveFrameHandle(msg: can.Message, bus: int):
    global Receive_Info, BS
    if msg.dlc == 8 or msg.dlc == 12 or msg.dlc == 16 or msg.dlc == 20 or msg.dlc == 24 or msg.dlc == 32 or msg.dlc == 48 or msg.dlc == 64:
        if msg.dlc == Receive_Info.RX_DL and ((msg.data[0] & 0x0F == Receive_Info.SN_cnt + 1) or (msg.data[0] & 0x0F == 0 and Receive_Info.SN_cnt == 15)):
            
            Receive_Info.SN_cnt = msg.data[0] & 0x0F
            Receive_Info.data_hex_buf.clear()
            Receive_Info.data_hex_buf.extend(msg.data[1:])
            Receive_Info.BS_cnt -= 1
            Receive_Info.data_str_buffer += ascii_list_to_string(Receive_Info.data_hex_buf, DUM_BYTE)
            Receive_State_Info.CF = 1
            Receive_State_Info.time_Cr = time.time()
            
            print(f"COUNTER: {Receive_Info.BS_cnt}")
            
            print(f"Bus {bus} Receive CS {Receive_Info.SN_cnt}: {Receive_Info.data_str_buffer}")
            if len(Receive_Info.data_str_buffer) < Receive_Info.data_length:
                # print(f"{len(Receive_Info.data_str_buffer)} and {Receive_Info.data_length}")
                # print("send FC")
                if Receive_Info.BS_cnt == 0:
                    Receive_Info.BS_cnt = BS
                    
                    # FC_frame = Frame(frametype=FC, length=8, FS = WAIT, BS = BS, STmin = STmin)           
                    # msg_send_fc = can.Message(arbitration_id=0xAA, data=FC_frame.framefomart, is_extended_id=False)
                    # #start N_Ar
                    # Receive_State_Info.check_Ar()
                    # Receive_State_Info.time_Ar = time.time()
                    # if bus == 1:
                    #     SendMsg(bus1, msg_send_fc)
                    # else:
                    #     SendMsg(bus2, msg_send_fc)

                    FC_frame = Frame(frametype=FC, length=8, FS = CTS, BS = BS, STmin = STmin)           
                    msg_send_fc = can.Message(arbitration_id=0xAA, data=FC_frame.framefomart, is_extended_id=False)

                    #start N_Ar
                    Receive_State_Info.check_Ar()
                    Receive_State_Info.time_Ar = time.time()
                    if bus == 1:
                        SendMsg(bus1, msg_send_fc)
                    else:
                        SendMsg(bus2, msg_send_fc)
                    Receive_State_Info.send_FC = 1
            else:
                print("Complete receive")
                Receive_State_Info.is_done = 1
        else:
            print(f"Bus {bus} Receive CS fail1 {msg.data[0]}, {Receive_Info.SN_cnt + 1} {(msg.data[0] & 0x0F == Receive_Info.SN_cnt + 1)} {msg.data[0] == 0 and Receive_Info.SN_cnt == 15}")
    else:
        print(f"Bus {bus} Receive CS fail3")

def FlowControlHandle(msg: can.Message, bus: int):
    global Transmit_Info, Transmit_State_Info
    if msg.dlc == 8:
        if msg.data[0] & 0x0F == CTS:
            Transmit_State_Info.receive_FC = 1
            prGreen(f"receive_FC {time.time()}")
            # Transmit_State_Info.time_Cs = time.time()
            Transmit_Info.BS_cnt = msg.data[1]
            Transmit_Info.STmin = msg.data[2]
            prGreen(f"Bus {bus} Receive CTS ")
        elif msg.data[0] &0x0F == WAIT:
            prGreen(f"Bus {bus} Receive WAIT")
            # reload Bs
        elif msg.data[0] &0x0F == OVFLW:  
            prGreen(f"Bus {bus} Overflow, abort connection")
    else: 
        prGreen(f"Bus {bus} Receive FC fail, abort connection")

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
            # print("Single frame")
            SingleFrameHandle(msg, 2)
        elif msg.data[0] >> 4 == 1:
            # print("First frame")
            FirstFrameHandle(msg, 2)
        elif msg.data[0] >> 4 == 2:
            # print("Consecutive frame")
            ConsecutiveFrameHandle(msg, 2)
        elif msg.data[0] >> 4 == 3:
            # print("Flow control")
            FlowControlHandle(msg, 2)

class ListenerHandlebus1(can.Listener):
    def on_message_received(self, msg: can.Message):
        print(f"Receive message bus 1: {msg}")
        if msg.data[0] >> 4 == 0:
            # print("Single frame")
            SingleFrameHandle(msg, 1)
        elif msg.data[0] >> 4 == 1:
            # print("First frame")
            FirstFrameHandle(msg, 1)
        elif msg.data[0] >> 4 == 2:
            # print("Consecutive frame")
            ConsecutiveFrameHandle(msg, 1)
        elif msg.data[0] >> 4 == 3:
            # print("Flow control")
            FlowControlHandle(msg, 1)

def Transmit(bus: int, id: int, TX_DL: int , data_buf: list, length: int, is_fd: bool = False):
    global Transmit_Info, bus1, bus2, Transmit_State_Info
    index = last_index = 0           #begin index of new frame in buffer
    
    if (length < 7 and TX_DL == 8):                         #single frame <= 8
        send_frame = Frame(frametype=SF, length=TX_DL, data=data_buf)
        msg_send = can.Message(arbitration_id=id, data=send_frame.framefomart, is_fd=is_fd)

        #start N_As
        Transmit_State_Info.time_As = time.time()
        Transmit_State_Info.check_As()
        while Transmit_State_Info.result == 0:              # wait check N_Bs timeout
            pass
        if Transmit_State_Info.result == 2:
            return
        # #print(Transmit_State_Info.check_request)
        if bus == 1:
            SendMsg(bus1, msg_send)
        else:
            SendMsg(bus2, msg_send)
        Transmit_State_Info.send_FF = 1

    elif (length < TX_DL - 2 and ( TX_DL == 12 or TX_DL == 16 or TX_DL == 20 or TX_DL == 24 or TX_DL == 32 or TX_DL == 48 or TX_DL == 64)):         #SF > 8
        send_frame = Frame(frametype=SF, length=TX_DL, data=data_buf)
        msg_send = can.Message(arbitration_id=id, data=send_frame.framefomart, is_fd=True)

        #start N_As
        Transmit_State_Info.time_As = time.time()
        Transmit_State_Info.check_As()
        #print(Transmit_State_Info.check_request)
        if bus == 1:
            SendMsg(bus1, msg_send)
        else:
            SendMsg(bus2, msg_send)
        Transmit_State_Info.send_FF = 1
        while Transmit_State_Info.result == 0:              # wait check N_Bs timeout
            pass
        if Transmit_State_Info.result == 2:
            return
    else:
        T_thread.start()
        index = TX_DL - 2
        send_frame = Frame(frametype=FF, length=TX_DL, data=data_buf[:index], DL=length)
        msg_send = can.Message(arbitration_id=id, data=send_frame.framefomart, is_fd=True)
        Transmit_Info.SN_cnt += 1

        #start N_As
        prGreen("start N_As")
        Transmit_State_Info.time_As = time.time()
        Transmit_State_Info.check_As()
        if bus == 1:
            SendMsg(bus1, msg_send)
        else:
            SendMsg(bus2, msg_send)
        Transmit_State_Info.send_FF = 1
        # print(Transmit_State_Info.check_request)
        while Transmit_State_Info.result == 0:              # wait check N_Bs timeout
            pass
        if Transmit_State_Info.result == 2:
            return
        #start N_Bs and wait FC
        prGreen("Check Bs")
        Transmit_State_Info.check_Bs()
        Transmit_State_Info.time_Bs = time.time()
        prGreen(f"time Bs start {Transmit_State_Info.time_Bs}")

        while Transmit_State_Info.result == 0:              # wait check N_Bs timeout
            pass
        prGreen(f"Check Bs done {Transmit_State_Info.result}")
        if (Transmit_State_Info.result == 10):
            while index < length and Transmit_State_Info.is_done == 0:
                Transmit_State_Info.is_done = 0
                time.sleep(CalculateSTmin(Transmit_Info.STmin))
                # Transmit_State_Info.receive_FC = 0
                if index + TX_DL - 1 <= length - 1:              # check
                    last_index = index
                    index = index + TX_DL - 1
                    send_frame = Frame(frametype=CF, length=TX_DL, data=data_buf[last_index:index], SN=Transmit_Info.SN_cnt)
                    Transmit_Info.SN_cnt += 1
                    if Transmit_Info.SN_cnt == 16:
                        Transmit_Info.SN_cnt = 0
                    Transmit_Info.BS_cnt -= 1
                    msg_send = can.Message(arbitration_id=id, data=send_frame.framefomart, is_fd=True)

                    # start N_As
                    prGreen(f"Start As {Transmit_Info.SN_cnt} {Transmit_Info.BS_cnt}")
                    Transmit_State_Info.check_As()
                    Transmit_State_Info.time_As = time.time()
                    prGreen(Transmit_State_Info.check_request)
                    if bus == 1:
                        SendMsg(bus1, msg_send)
                    else:
                        SendMsg(bus2, msg_send)
                    Transmit_State_Info.send_CF = 1
                    prGreen(f"?????{Transmit_State_Info.send_CF}")
                    while Transmit_State_Info.result == 0:              # wait check N_Bs timeout
                        pass
                    if Transmit_State_Info.result == 2:
                        return
                    prGreen("send CF")
                else:
                    send_frame = Frame(frametype=CF, length=TX_DL, data=data_buf[index:], SN=Transmit_Info.SN_cnt)
                    Transmit_Info.SN_cnt += 1
                    if Transmit_Info.SN_cnt == 16:
                        Transmit_Info.SN_cnt = 0
                    Transmit_Info.BS_cnt -= 1
                    Transmit_State_Info.is_done = 1
                
                # check N_Cs timeout (wait CF send)

                    msg_send = can.Message(arbitration_id=id, data=send_frame.framefomart, is_fd=True)
                    
                    # start N_As
                    prGreen(f"Start As 1 {Transmit_Info.SN_cnt} {Transmit_Info.BS_cnt}")
                    Transmit_State_Info.time_As = time.time()
                    Transmit_State_Info.check_As()
                    # #print(Transmit_State_Info.check_request)
                    if bus == 1:
                        SendMsg(bus1, msg_send)
                    else:
                        SendMsg(bus2, msg_send)
                    Transmit_State_Info.send_CF = 1
                    while Transmit_State_Info.result == 0:              # wait check N_Bs timeout
                        pass
                    if Transmit_State_Info.result == 2:
                        return
                
                # if Transmit_State_Info.is_done == 1:
                #     break
                if Transmit_Info.BS_cnt == 0:
                    Transmit_State_Info.time_Bs = time.time()
                    prGreen(f"time Bs start {Transmit_State_Info.time_Bs}")
                    Transmit_State_Info.check_Bs()
                    while Transmit_State_Info.result == 0:
                        pass
                    prGreen(f"Check Bs done {Transmit_State_Info.result}")
                else:
                    # Transmit_State_Info.time_Cs = time.time()
                    # Transmit_State_Info.check_Cs()
                    # time.sleep(CalculateSTmin(Transmit_Info.STmin))
                    pass

                # while Transmit_State_Info.receive_FC == 0 and Transmit_Info.BS_cnt == 0:          # wait to receive FC when transmit number frame = blocksize
                #     pass

def ReceiveHanle():
    global Receive_State_Info, Receive_Info
    Receive_Timeout = RcvTimeout(0.2, 0.2, 0.5)
    Receive_State_Info.is_done = 0

    while Receive_State_Info.is_done == 0:
        #check N_Ar timeout (receive FC)
        if Receive_State_Info.check_request == 1:          #N_Ar check
            # start N_ar when start send FC
            while Receive_State_Info.send_FC == 0 and time.time() - Receive_State_Info.time_Ar < Receive_Timeout.Ar:
                pass
            if Receive_State_Info.send_FC == 1:
                print("Send FC from receiver")
                Receive_State_Info.result = 1
                Receive_State_Info.check_request = 0
                Receive_State_Info.send_FC = 0
            else:
                print("N_Ar timeout. Abort connection")
                Receive_State_Info.is_done = 1
                Receive_State_Info.result = 2
                Receive_State_Info.check_request = 0
        elif Receive_State_Info.check_request == 2:        #N_Br check, start when receive last CF in block and receive FF, edit later
            while Receive_State_Info.available_receive == 0 and time.time() - Receive_State_Info.time_Br < Receive_Timeout.Br:
                pass
            if Receive_State_Info.receive_FC == 1:
                print("Send FC(CTS)")
                Receive_State_Info.result = 1
                Receive_State_Info.WFT_cnt = WFT
            else:
                print("N_Br Timeout, reload N_Br")
                Receive_State_Info.time_Br = time.time()
                Receive_State_Info.WFT_cnt -= 1
                if Receive_State_Info.WFT_cnt == -1:
                    print("Reach WFT limit. Abort conection")
                    Receive_State_Info.result = 2
                    Receive_State_Info.is_done = 1
                    Receive_State_Info.check_request = 0
                    Receive_State_Info.WFT_cnt = WFT
        
        
        elif Receive_State_Info.check_request == 3:     #N_Cr check
            #start N_Cs when after send FC, reload when receive CF(not last frame in block)
            while Receive_State_Info.receive_CF == 0 and time.time() - Receive_State_Info.time_Cr < Receive_Timeout.Cr:
                pass
            if Receive_State_Info.receive_CF == 1:
                print("Receive CF")
                Receive_State_Info.result = 1
            else:
                print("N_Cr timeout. Abort connection")
                Receive_State_Info.is_done = 1
                Receive_State_Info.result = 2

def TransmitHanle():
    global Transmit_Info, Transmit_State_Info
    Transmit_State_Info.receive_FC = 0
    Transmit_Timeout = TsmTimeout(0.2, 1, 0.2)
    while Transmit_State_Info.is_done == 0:
        #check N_Bs timeout (receive FC)
        if Transmit_State_Info.check_request == 1:          #N_As check
            while (Transmit_State_Info.send_FF == 0 and Transmit_State_Info.send_CF == 0) and time.time() - Transmit_State_Info.time_As < Transmit_Timeout.As:
                pass
            if Transmit_State_Info.send_FF == 1 or Transmit_State_Info.send_CF == 1:
                prGreen("Send frame from transmiter")
                Transmit_State_Info.result = 11
                Transmit_State_Info.send_FF = Transmit_State_Info.send_CF = 0
                Transmit_State_Info.check_request = 0
            else:
                prGreen("N_As timeout. Abort connection")
                # time.sleep(1)
                Transmit_State_Info.check_request = 0
                Transmit_State_Info.is_done = 1
                Transmit_State_Info.result = 2
        elif Transmit_State_Info.check_request == 2:        #N_Bs check
            Transmit_State_Info.check_request = Transmit_State_Info.result = 0
            while Transmit_State_Info.receive_FC == 0 and time.time() - Transmit_State_Info.time_Bs < Transmit_Timeout.Bs:
                pass
            prGreen(f"{Transmit_State_Info.receive_FC} {time.time() - Transmit_State_Info.time_Bs < Transmit_Timeout.Bs} {time.time()} {Transmit_State_Info.time_Bs}")
            if Transmit_State_Info.receive_FC == 1:
                prGreen("Receive FC(CTS)")
                Transmit_State_Info.result = 10
                Transmit_State_Info.receive_FC = 0
                Transmit_State_Info.check_request = 0
            else:
                prGreen("N_Bs Timeout, abort connection")
                Transmit_State_Info.is_done = 1
                Transmit_State_Info.result = 2
                Transmit_State_Info.check_request = 0
        elif Transmit_State_Info.check_request == 3:
            pass #latter
    if (Transmit_State_Info.is_done == 1):
        prGreen("Transmit complete")

def SendMsg(bus, msg: can.Message, timeout: float = 0.0, flg: int = 0):
    global Transmit_State_Info
    # Transmit_State_Info.check_As()
    # Transmit_State_Info.time_As = time.time()
    # sleep in here  
    # time.sleep(0.3)
    bus.send(msg)

def ReceiveMsg(timeout: float = 0.0, flg: int = 0):
    rcv_time = time.time()

    while flg == 1 or time.time() - rcv_time <= timeout:
        pass
    if flg == 1:
        flg == 0
        return True
    else:
        return False


R_thread = threading.Thread(target=ReceiveHanle)
T_thread = threading.Thread(target=TransmitHanle)

bus1 = can.ThreadSafeBus('test', interface='virtual')
bus2 = can.ThreadSafeBus('test', interface='virtual')


Transmit_Info = Info()
Receive_Info = Info()

Receive_State_Info = Receive_State()
Transmit_State_Info = Transmit_State()

# mutex_send_buf = threading.Lock()
# mutex_rcv_buf = threading.Lock()

if __name__ == "__main__":

    notifier2 = can.Notifier(bus2, [ListenerHandlebus2()])
    notifier1 = can.Notifier(bus1, [ListenerHandlebus1()])
    send_data_b ="""Trump's visit to his golf course in West Palm Beach was not on his public schedule, acting U.S. Secret Service Director Ronald Rowe told reporters on Monday afternoon, and it was not clear whether the suspect knew Trump would be there.
The Secret Service opened fire after an agent sweeping the course saw a rifle barrel poking out of the bushes a few hundred yards away from the former president, who was on the fairway of the fifth hole.
"All of a sudden we heard shots being fired in the air. I guess probably four or five," Trump said during an event on X Spaces. "Secret Service knew immediately it was bullets, and they grabbed me. ... We got into the carts and we moved along pretty, pretty good. I was with an agent, and the agent did a fantastic job."
While praising the Secret Service agents, he added: "We do need more people on my detail."
The gunman fled in a sports utility vehicle, according to court papers on Monday. Officers found a loaded assault-style rifle with a scope, a digital camera and a plastic bag of food left behind.
A suspect, identified on Monday as Ryan Routh, 58, was arrested about 40 minutes later driving north on Interstate 95. The license plate on his vehicle had been reported stolen from another car.
Records show a phone associated with Routh was located at the golf course starting at 1:59 a.m. (0559 GMT) on Sunday morning, 11-1/2 hours before the incident.
The suspect was on the "public side" of a fence along the golf course's boundary, Rowe said.
Routh was the subject of a 2019 tip to the FBI alleging that he was a convicted felon who illegally possessed a firearm, Jeffrey Veltri, the agent in charge of the FBI's Miami field office, told reporters.
The complainant was unable to verify the information when the FBI investigated the tip, Veltri said.
Routh made a brief appearance in federal court in West Palm Beach on Monday, where he was charged with possession of a firearm as a convicted felon and possession of a firearm with an obliterated serial number. More charges could follow.
The defendant invoked his right to an attorney when investigators sought to question him, Rowe said.
In 2002, Routh pleaded guilty in North Carolina to possession of an unregistered fully automatic gun, defined in state law as a weapon of mass destruction, according to the county district attorney's office, and was sentenced to probation. He was also convicted of possessing stolen goods in 2010.
The Secret Service, which protects U.S. presidents, presidential candidates and other high-level dignitaries, has been under intense scrutiny since the earlier attempt on Trump's life.
That led to the resignation of Director Kimberly Cheatle. The service bolstered Trump's security detail following the July 13 attack, in which the gunman was shot dead by responding agents.
The agency "needs more help," including possibly more personnel, Biden told reporters on Monday, adding: "Thank God the president's OK."
House of Representatives Speaker Mike Johnson, who convened a bipartisan task force to investigate the first assassination attempt, told Fox News that Congress would also examine the latest incident, saying, "We need accountability."
Rowe, who took over after Cheatle's resignation in July, told Congress on July 30 he was "ashamed" of security lapses in the earlier attack.
Routh is a staunch supporter of Ukraine and traveled there after Russia's 2022 invasion, seeking to recruit foreign fighters. Ukrainian officials distanced themselves from Routh on Monday, and The International Legion, where many foreign fighters in Ukraine serve, said it had no links with Routh.
Harris has promised unwavering support for Ukraine if elected.
Trump has expressed skepticism about the amount of aid the U.S. has provided Ukraine and has vowed to end the war immediately if elected. He told Reuters last year that Ukraine might have to cede some territory to gain peace."""

    # send_data_b = "12345612345671234567123456712345671234567123456712345678"
    send_data_a = "Hello"
    try:
        while 1:
            choice = input()
            if choice == 's1':
                Transmit(bus=1, id=0x012, TX_DL=8, data_buf=string_to_ascii_list(send_data_b), length=len(send_data_b), is_fd= True)
            elif choice == 's2':
                Transmit(bus=1, id=0x012, TX_DL=8, data_buf=string_to_ascii_list(send_data_a), length=len(send_data_a), is_fd= True)
            else:
                print("quit")
                break
        Receive_State_Info.is_done = 1
        Transmit_State_Info.is_done = 1
        T_thread.join()
        R_thread.join()
    except KeyboardInterrupt:
        Receive_State_Info.is_done = 1
        Transmit_State_Info.is_done = 1
        T_thread.join()
        R_thread.join() 
        notifier1.stop()
        notifier2.stop()
        # shutdown bus
        bus1.shutdown()
        bus2.shutdown()