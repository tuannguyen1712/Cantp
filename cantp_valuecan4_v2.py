import time
import can
import threading
 
def prGreen(skk):
    print("\033[92m {}\033[00m" .format(skk))
def prCyan(skk):
    print("\033[96m {}\033[00m".format(skk))
def prYellow(skk):
    print("\033[93m {}\033[00m" .format(skk))
def prBlue(skk):
    print("\033[94m {}\033[00m".format(skk))
def prRed(skk):
    print("\033[91m {}\033[00m".format(skk))
 
SF = 0          # single frame
FF = 1          # first frame
CF = 2          # consecutive frame
FC = 3          # flow control        
 
CTS = 0         # Clear to send
WAIT = 1        # wait
OVFLW = 2         # overflow
 
DUM_BYTE = 0x00
ID_SEND = 0x089
ID_RECEIVE1 = ID_TRANSMIT1 = 0x111
ID_RECEIVE2 = ID_TRANSMIT2 = 0x222
ID_RECEIVE3 = ID_TRANSMIT3 = 0x003
 
WFT = 3                 # maximum FC(WAIT) in row
BS = 5
STmin = 100            #127 ms
 
bus = can.interface.Bus(interface='neovi', channel=1, bitrate=500000, receive_own_messages = False)
# bus1 = can.interface.Bus('test', interface='virtual')
# bus2 = can.interface.Bus('test', interface='virtual')
 
class Receive_Info():
    def __init__(self) -> None:
        self.available_receive = 0                  # available to send , timeout will send FC(WAIT)
        self.receive_FF = 0
        self.receive_CF = 0
        self.send_FC = 0
 
        self.WFT_cnt = WFT
        self.is_done = 1
        self.time_Ar = 0
        self.time_Br = 0
        self.time_Cr = 0
       
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
        self.STmin = 0
 
class Transmit_Info():
    def __init__(self) -> None:
        self.send_frame = 0
        self.receive_FC = 0
        self.is_done = 0
        self.time_As = 0
        self.time_Bs = 0
        self.time_Cs = 0
 
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
        self.STmin = 0
        self.last_frame = 0
 
class RcvTimeout():
    def __init__(self, Ar:float = 0, Br: float = 0, Cr: float = 0) -> None:
        self.Ar = Ar
        self.Br = Br
        self.Cr = Cr
 
class TsmTimeout():
    def __init__(self, As:float = 0, Bs: float = 0, Cs: float = 0) -> None:
        self.As = As
        self.Bs = Bs
        self.Cs = Cs
       
Receive_Timeout = RcvTimeout(0.2, 0.2, 0.4)
Transmit_Timeout = TsmTimeout(0.2, 0.4, 0.4)
 
# Receive_Timeout = RcvTimeout(4, 4, 8)
# Transmit_Timeout = TsmTimeout(4, 8, 8)
 
Transmit_Info_Dict = {
    ID_TRANSMIT1: Transmit_Info(),
    ID_TRANSMIT2: Transmit_Info(),
    ID_TRANSMIT3: Transmit_Info(),
}
 
Receive_Info_Dict = {
    ID_RECEIVE1: Receive_Info(),
    ID_RECEIVE2: Receive_Info(),
    ID_RECEIVE3: Receive_Info(),
}
 
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
 
def SingleFrameHandle(msg: can.Message, Receive_Info: Receive_Info, bus):
    Receive_Info.reset_param()
    if msg.dlc <= 8:
        if msg.data[0] & 0x0F == msg.dlc - 1:
            print(f"Bus  Receive SF {ascii_list_to_string(list(msg.data), DUM_BYTE, 1)}")
            Receive_Info.data_str_buffer = ascii_list_to_string(list(msg.data), DUM_BYTE, 1)
            Receive_Info.SF = 1
        else:
            print("Bus  Receive Error")
    elif msg.dlc == 12 or msg.dlc == 16 or msg.dlc == 20 or msg.dlc == 24 or msg.dlc == 32 or msg.dlc == 48 or msg.dlc == 64:
        if msg.data[0] & 0x0F == 0 and msg.data[1] == msg.dlc - 2:
            print(f"Bus  Receive SF {ascii_list_to_string(list(msg.data), DUM_BYTE, 2)}")
            Receive_Info.data_str_buffer = ascii_list_to_string(list(msg.data), DUM_BYTE, 1)
            Receive_Info.SF = 1
        else:
            print(f"Bus  Receive Error")
    else:
        print(f"Bus  Receive SF Fail")
 
def FirstFrameHandle(msg: can.Message, Receive_Info: Receive_Info, bus):
    global BS, STmin, Receive_Timeout
    Receive_Info.reset_param()
    TxTask = threading.Thread(target=FC_TransmitTask, args=(bus, msg.arbitration_id, Receive_Info, Receive_Timeout))
   
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
            print(f"Bus  Receive FF {Receive_Info.data_str_buffer}")
 
            Receive_Info.receive_FF = 1
            Receive_Info.is_done = 0
            Receive_Info.available_receive = 1
            TxTask.start()
        else:
            print(f"Bus  Bus  Receive FF 1fail")
    else:
        Receive_Info.data_length = (msg.data[2] << 24) | (msg.data[3] << 16) | (msg.data[4] << 8) | msg.data[5]
        if Receive_Info.data_length != 0:
            Receive_Info.BS_cnt = BS
            Receive_Info.SN_cnt = 0
            Receive_Info.RX_DL = msg.dlc
            Receive_Info.data_hex_buf.clear()
            Receive_Info.data_str_buffer = ""
            Receive_Info.data_hex_buf.extend(msg.data[6:])
            Receive_Info.data_str_buffer += ascii_list_to_string(Receive_Info.data_hex_buf, DUM_BYTE)
            print(f"Bus  Receive FF {Receive_Info.data_str_buffer}")
 
            Receive_Info.receive_FF = 1
            Receive_Info.is_done = 0
            Receive_Info.available_receive = 1              #clear this flag to reach WFTlimit
            # Receive_Info.available_receive = 0             # BRT
            TxTask.start()
        else:
            print(f"Bus  Receive FF 2fail")
 
def ConsecutiveFrameHandle(msg: can.Message, Receive_Info: Receive_Info, bus):
    global BS
    if (msg.dlc == 8 or msg.dlc == 12 or msg.dlc == 16 or msg.dlc == 20 or msg.dlc == 24 or msg.dlc == 32 or msg.dlc == 48 or msg.dlc == 64) \
        and Receive_Info.data_length - len(Receive_Info.data_str_buffer) >= Receive_Info.RX_DL and Receive_Info.is_done == 0:
        if (msg.dlc == Receive_Info.RX_DL and ((msg.data[0] & 0x0F == Receive_Info.SN_cnt + 1) or (msg.data[0] & 0x0F == 0 and Receive_Info.SN_cnt == 15))):
           
            Receive_Info.SN_cnt = msg.data[0] & 0x0F
            Receive_Info.BS_cnt -= 1
            Receive_Info.data_hex_buf.clear()
            Receive_Info.data_hex_buf.extend(msg.data[1:])
            Receive_Info.data_str_buffer += ascii_list_to_string(Receive_Info.data_hex_buf, DUM_BYTE)
            print(f"Bus  Receive CS num {Receive_Info.SN_cnt}, BS cnt {Receive_Info.BS_cnt}")
            if Receive_Info.BS_cnt != 0:
                Receive_Info.time_Cr = time.time()
            else:
                Receive_Info.available_receive = 1              #clear this flag to reach WFTlimit
                # Receive_Info.available_receive = 0             # BRT2
                Receive_Info.receive_CF = 1
        else:
            print(f"Bus  Receive CS fail1 {msg.data[0]}, {Receive_Info.SN_cnt + 1} {(msg.data[0] & 0x0F == Receive_Info.SN_cnt + 1)} {msg.data[0] == 0 and Receive_Info.SN_cnt == 15}")
    elif Receive_Info.data_length - len(Receive_Info.data_str_buffer) < Receive_Info.RX_DL and Receive_Info.is_done == 0:
        Receive_Info.data_hex_buf.clear()
        Receive_Info.data_hex_buf.extend(msg.data[1:])
        Receive_Info.data_str_buffer += ascii_list_to_string(Receive_Info.data_hex_buf, DUM_BYTE)
        prCyan(f"Receive data {len(Receive_Info.data_str_buffer)}: {Receive_Info.data_str_buffer} ")
        prGreen(f"Complete receive msg {msg.arbitration_id}")
        Receive_Info.receive_CF = 1
        Receive_Info.is_done = 1
    else:
        print(f"Bus  Receive CS fail3 {Receive_Info.data_str_buffer} {Receive_Info.data_length} {len(Receive_Info.data_str_buffer)}")
 
def FlowControlHandle(msg: can.Message, Transmit_Info: Transmit_Info, bus):
    if msg.dlc == 8:
        if msg.data[0] & 0x0F == CTS:
            Transmit_Info.receive_FC = 1
            prBlue(f"receive_FC {msg.arbitration_id} {time.time()} ")
            Transmit_Info.BS_cnt = msg.data[1]
            Transmit_Info.STmin = msg.data[2]
        elif msg.data[0] &0x0F == WAIT:
            prBlue(f"Bus  {msg.arbitration_id} Receive WAIT")
            # reload Bs
            Transmit_Info.time_Bs = time.time()
        elif msg.data[0] &0x0F == OVFLW:  
            prBlue(f"Bus  Overflow, abort connection  {msg.arbitration_id}")
    else:
        prBlue(f"Bus  Receive FC fail, abort connection  {msg.arbitration_id}")
 
def string_to_ascii_list(str):
    return [ord(char) for char in str]
 
def ascii_list_to_string(ascii_list, dummy_byte, start_index=0):
    return ''.join(chr(byte) for byte in ascii_list[start_index:] if byte != dummy_byte)
 
def replace_elements(list1, list2, n):
    num_elements_to_replace = min(len(list1) - n, len(list2))
    list1[n:n + num_elements_to_replace] = list2[:num_elements_to_replace]
    return list1
 
def CalculateSTmin(STmin: int):
    if STmin <= 127:
        return STmin / 1000
    elif STmin >= 0xF1 and STmin <= 0xF9:
        return (STmin & 0x0F) / 10000
 
class ListenerHandlebus(can.Listener):
    global bus, Receive_Info_Dict
    def on_message_received(self, msg: can.Message):
        print(f"Receive message bus 2: {msg}")
        if msg.data[0] >> 4 == 0:
            # print("Single frame")
            SingleFrameHandle(msg, Receive_Info_Dict[msg.arbitration_id], bus)
        elif msg.data[0] >> 4 == 1:
            # print("First frame")
            FirstFrameHandle(msg=msg, Receive_Info = Receive_Info_Dict[msg.arbitration_id], bus=bus)
        elif msg.data[0] >> 4 == 2:
            # print("Consecutive frame")
            ConsecutiveFrameHandle(msg=msg, Receive_Info = Receive_Info_Dict[msg.arbitration_id], bus=bus)
        elif msg.data[0] >> 4 == 3:
            # print("Flow control")
            FlowControlHandle(msg,Transmit_Info_Dict[msg.arbitration_id], bus)
 
def TransmitTask(bus, id: int, Transmit_Info: Transmit_Info, Transmit_Timeout: TsmTimeout, \
             TX_DL: int , data_buf: list, length: int, is_fd: bool = False):
    Transmit_Info.is_done = 0
    Transmit_Info.reset_param()
    index = last_index = 0           #begin index of new frame in buffer
    ret = False
    if (length < 7 and TX_DL == 8):                         #single frame <= 8
        send_frame = Frame(frametype=SF, length=TX_DL, data=data_buf)
        msg_send = can.Message(arbitration_id=id, data=send_frame.framefomart, is_fd=is_fd)
 
        #start N_As
        prBlue(f"start N_As {id}")
        # dont set this flag if want to get N_As timeout
        Transmit_Info.send_frame = 1
        ret = SendMsg(bus=bus, msg=msg_send, timeout=Transmit_Timeout.As, flag = Transmit_Info.send_frame)
        if ret == False:
            return
        else:
            Transmit_Info.send_frame = 0
 
    elif (length < TX_DL - 2 and ( TX_DL == 12 or TX_DL == 16 or TX_DL == 20 or TX_DL == 24 or TX_DL == 32 or TX_DL == 48 or TX_DL == 64)):         #SF > 8
        send_frame = Frame(frametype=SF, length=TX_DL, data=data_buf)
        msg_send = can.Message(arbitration_id=id, data=send_frame.framefomart, is_fd=True)
 
        prBlue(f"start N_As {id}")
        # dont set this flag if want to get N_As timeout
        Transmit_Info.send_frame = 1
        ret = SendMsg(bus=bus, msg=msg_send, timeout=Transmit_Timeout.As, flag = Transmit_Info.send_frame)    
        if ret == False:
            return
        else:
            Transmit_Info.send_frame = 0
    else:
        if (length <= 4095):
            index = TX_DL - 2
        else:
            index = TX_DL - 6
        send_frame = Frame(frametype=FF, length=TX_DL, data=data_buf[:index], DL=length)
        msg_send = can.Message(arbitration_id=id, data=send_frame.framefomart, is_fd=True)
        Transmit_Info.SN_cnt += 1
   
        #start N_As
        prBlue(f"start N_As {id}")
        # dont set this flag if want to get N_As timeout
        Transmit_Info.send_frame = 1              # get TxComfirmation, AST1
        ret = SendMsg(bus=bus, msg=msg_send, timeout=Transmit_Timeout.As, flag = Transmit_Info.send_frame)
        if ret == False:        #N_As occurrence
            prYellow(f"N_As timeout {id}")
            Transmit_Info.is_done = 1
            return
        else:
            Transmit_Info.send_frame = 0
        prBlue(f"send FF  {id}")
        # start N_Bs and wait FC
        prBlue(f"Check Bs {id}")                      
        ret = ReceiveFC(Transmit_Timeout=Transmit_Timeout, Transmit_Info=Transmit_Info)
        if ret == False:        #N_Bs occurrence
            prYellow(f"N_Bs timeout{id}")
            Transmit_Info.is_done = 1
            return
 
        while index < length and Transmit_Info.is_done == 0:
            Transmit_Info.is_done = 0
            time.sleep(CalculateSTmin(Transmit_Info.STmin))
            if index + TX_DL - 1 < length:              # check
                last_index = index
                index = index + TX_DL - 1
                send_frame = Frame(frametype=CF, length=TX_DL, data=data_buf[last_index:index], SN=Transmit_Info.SN_cnt)
                msg_send = can.Message(arbitration_id=id, data=send_frame.framefomart, is_fd=True)
                prBlue(f"start N_As {Transmit_Info.SN_cnt} {id}")
                Transmit_Info.SN_cnt += 1
                if Transmit_Info.SN_cnt == 16:
                    Transmit_Info.SN_cnt = 0
                Transmit_Info.BS_cnt -= 1
                # start N_As
                # dont set this flag if want to get N_As timeout
                Transmit_Info.send_frame = 1                   # get TxComfirmation           AST1
                ret = SendMsg(bus=bus, msg=msg_send, timeout=Transmit_Timeout.As, flag = Transmit_Info.send_frame)
                prBlue(f"send CF {id} {time.time()} ")
 
                if ret == False:        #N_As occurrence
                    prYellow(f"N_As timeout {id}")
                    Transmit_Info.is_done = 1
                    return
                else:
                    Transmit_Info.send_frame = 0
            elif Transmit_Info.is_done == 0:
                send_frame = Frame(frametype=CF, length=find_min_greater(length - index), data=data_buf[index:], SN=Transmit_Info.SN_cnt)
                Transmit_Info.SN_cnt += 1
                if Transmit_Info.SN_cnt == 16:
                    Transmit_Info.SN_cnt = 0
                Transmit_Info.BS_cnt -= 1
                Transmit_Info.is_done = 1
                msg_send = can.Message(arbitration_id=id, data=send_frame.framefomart, is_fd=True)
                # start N_As
                prBlue(f"start N_As {id}")
                # dont set this flag if want to get N_As timeout
                Transmit_Info.send_frame = 1                    # AST2
                ret = SendMsg(bus=bus, msg=msg_send, timeout=Transmit_Timeout.As, flag = Transmit_Info.send_frame)
                if ret == False:        #N_As occurrence
                    prYellow(f"N_As timeout {id}")
                    Transmit_Info.is_done = 1
                    return
                else:
                    Transmit_Info.send_frame = 0
               
               
            if Transmit_Info.BS_cnt == 0 and Transmit_Info.is_done == 0:
                prBlue(f"Check Bs {id}")
                ret = ReceiveFC(Transmit_Timeout=Transmit_Timeout, Transmit_Info=Transmit_Info)
                if ret == False:        #N_Bs occurrence
                    prYellow(f"N_Bs timeout {id}")
                    Transmit_Info.is_done = 1
                    return
            else:
                # N_Cs timeout, handle later
                # Transmit_State_Info.time_Cs = time.time()
                # Transmit_State_Info.check_Cs()
                # time.sleep(CalculateSTmin(Transmit_Info.STmin))
                pass
        prGreen(f"Complete Transmit msg id {id}")
 
def SendMsg(bus: can.ThreadSafeBus, msg: can.Message, timeout: float = 0.0, flag: int = 0):
    tsm_time = time.time()
    while flag == 0 and time.time() - tsm_time <= timeout:
        pass
    if flag == 1:
        bus.send(msg)
        return True
    else:
        return False
 
def ReceiveFC(Transmit_Timeout: TsmTimeout, Transmit_Info: Transmit_Info):
    Transmit_Info.time_Bs = time.time()
    while Transmit_Info.receive_FC == 0 and time.time() - Transmit_Info.time_Bs <= Transmit_Timeout.Bs:
        pass
    if Transmit_Info.receive_FC == 1:
        Transmit_Info.receive_FC = 0
        return True
    else:
        print(f"{Transmit_Info.time_Bs} {time.time()}")
        return False
 
def CanTp_Transmit(bus, id, buffer, Transmit_Timeout, TX_DL, is_fd):
    Tx_Task = threading.Thread(target=TransmitTask, args=(bus, id, Transmit_Info_Dict[id], Transmit_Timeout,TX_DL,\
                                                    string_to_ascii_list(buffer), len(buffer), is_fd))
    Tx_Task.start()
 
def FC_TransmitTask(bus, id: int, Receive_Info: Receive_Info, Timeout_Info: RcvTimeout):
    global BS
    while Receive_Info.is_done == 0:
        if Receive_Info.receive_FF == 1 or Receive_Info.BS_cnt == 0:
           
            print(f"Start Br {id}")
            Receive_Info.receive_FF = 0
            ready_time = time.time()
            Receive_Info.WFT_cnt = WFT
            while Receive_Info.WFT_cnt != 0 and Receive_Info.is_done == 0:
                # clear Receive_Info.available_receive to get N_Br timeout or set Receive_Info.available_receive to avoid timeout
                while Receive_Info.available_receive == 0 and time.time() - ready_time <= Timeout_Info.Br:
                    pass
                if Receive_Info.available_receive == 1:
                    Receive_Info.available_receive = 0
                    Receive_Info.BS_cnt = BS
                    FC_frame = Frame(frametype=FC, length=8, FS = CTS, BS = BS, STmin = STmin)          
                    msg_send_fc = can.Message(arbitration_id=id, data=FC_frame.framefomart, is_extended_id=False)
                    print(f"start N_Ar {id} {msg_send_fc}")
                    # dont set this flag if want to get N_Ar timeout
                    Receive_Info.send_FC = 1                        # ART
                    ret = SendMsg(bus=bus, msg=msg_send_fc, timeout=Receive_Timeout.Ar, flag = Receive_Info.send_FC)
                    if ret == False:
                        prYellow(f"N_Ar timeout {id}")
                        Receive_Info.is_done = 1
                    else:
                        Receive_Info.send_FC = 0          
                    break
                else:
                    ready_time = time.time()
                    Receive_Info.WFT_cnt -= 1
                    FC_frame = Frame(frametype=FC, length=8, FS = WAIT, BS = BS, STmin = STmin)          
                    msg_send_fc = can.Message(arbitration_id=id, data=FC_frame.framefomart, is_extended_id=False)
       
                    print(f"start N_Ar {id}")
                    # dont set this flag if want to get N_Ar timeout
                    Receive_Info.send_FC = 1
                    ret = SendMsg(bus=bus, msg=msg_send_fc, timeout=Receive_Timeout.Ar, flag = Receive_Info.send_FC)
                    if ret == False:
                        prYellow(f"N_Ar timeout {id}")
                        Receive_Info.is_done = 1
                        break
                    else:
                        Receive_Info.send_FC = 0
            Receive_Info.receive_FF = 0
            if Receive_Info.WFT_cnt == 0:
                prYellow(f"WFT reach limit {id}")
                Receive_Info.is_done = 1
        else:
            print(f"Start N_Cr {id}")
            Receive_Info.time_Cr = time.time()
            Receive_Info.receive_CF = 0
            while Receive_Info.receive_CF == 0 and time.time() - Receive_Info.time_Cr <= Receive_Timeout.Cr:
                pass
            if Receive_Info.receive_CF == 1:              #receive last CF
                pass
            else:
                prYellow(f"Cr timeout {id} {time.time()} {Receive_Info.time_Cr}")
                Receive_Info.is_done = 1
 
def find_min_greater(x):
    values = [8, 12, 20, 24, 32, 48, 64]
    for value in values:
        if value > x:
            return value
    return None
 
def dynamic_config(new_WFT: int, new_BS: int, new_STmin: int):
    global WFT, BS, STmin
    WFT = new_WFT
    BS = new_BS
    STmin = new_STmin
 
 
if __name__ == "__main__":
 
    notifier = can.Notifier(bus, [ListenerHandlebus()])
 
    send_data_b ='''WASHINGTON, Sept 19 (Reuters) - Donald Trump and his Republican allies are ratcheting up baseless claims that the Nov. 5 U.S. presidential election could be skewed by widespread voting by non-citizens in a series of lawsuits that democracy advocates say are meant to sow distrust.
At least eight lawsuits have been filed challenging voter registration procedures in four of the seven swing states expected to decide the election contest between Trump and his Democratic rival, Vice President Kamala Harris.
Trump and his allies say the legal campaign, which includes a wide-ranging challenge to the citizenship status of voters in Arizona, is a defense of election integrity.
But their court filings offer little evidence of the phenomenon that independent studies show to be too rare to affect election results, legal experts said.
"The former president is trying to do what he's done the last three times he's run, and set up this 'If I win the election is valid and if I lose the election was rigged' narrative," said New Mexico Secretary of State Maggie Toulouse Oliver, a Democrat. Apart from his more recent presidential bids, Trump briefly ran in 2000 for the Reform Party.
The Trump campaign referred a request for comment to a spokesperson for the Republican National Committee, who said, "We believe our lawsuits will stop non-citizen voting, which threatens American votes."
It is a felony offense for a non-citizen to vote in a federal election and independent studies, opens new tab have shown it rarely happens.
Backers of Trump's strategy say that even one illegally cast ballot is too many.
Ohio Secretary of State Frank LaRose, a Republican, told a congressional panel last week that non-citizen voting is a rarity but that enforcement is necessary to keep it that way. He said his office recently identified nearly 600 non-citizens from state voter rolls that contain about 8 million registrants in total.
"We found 135 this year that had voted. We found another 400 that were registered but hadn't yet voted. And this idea that it's already illegal? It's illegal to hijack airplanes, but we don't get rid of the TSA," LaRose said.
A study of Trump's false claims of widespread non-citizen voting in the 2016 presidential election showed only 30 incidents among 23.5 million ballots cast, accounting for 0.0001% of the vote, opens new tab, the Brennan Center for Justice at New York University said.Federal law prohibits large-scale changes to voter rolls within 90 days of an election as well as purges that target particular class of voters, such as recently naturalized citizens, which the U.S. Justice Department reminded states of in an advisory last week.
That fact, democracy advocates say, show that Trump and his allies' strategy in pursuing these suits is not to secure major changes in the electorate, but to lay the groundwork for contesting individual state results if he loses, both in the courts and by trying to persuade elected officials to take action.
"Lawsuits over non-citizens on voter registration rolls are meritless. But they're part of a weaponized public relations campaign to erode confidence in elections," said Dax Goldstein, senior counsel for the nonpartisan States United Democracy Center, which promotes election security and fairness.
While national opinion polls, including the Reuters/Ipsos poll, show Harris with a slight lead over Trump, the race is close in the seven most competitive states: Arizona, Georgia, Michigan, Nevada, North Carolina, Pennsylvania and Wisconsin.
If a Harris win were to hang on just one or two states, a successful Trump challenge to a defeat in those states could be enough to reverse the election's outcome.
"Our elections are coming down to just dozens or hundreds of votes," said Republican Representative Anthony D'Esposito, who is seeking re-election this year in a toss-up New York district. "If one person that is not an American citizen has the ability to vote in our election, there is a serious problem.""The lawsuits, filed by the Trump campaign, the Republican National Committee, the allied America First Legal Foundation and Republican state attorneys general, primarily target state and county election processes, alleging that officials are failing to do enough to prevent non-citizens from registering or remaining on voter lists.
Rick Hasen, a law professor at the University of California, Los Angeles, and an expert on election law, said that the lawyers bringing these cases have reason to use more careful language than Trump and his allies do in discussing them.
"The public messaging is aimed at trying to convince the Republican base that Democrats are trying to steal elections and there's a lot of fraud," Hasen said. "Once you get to court, you are subject to the rules of court, and I think you see lawyers being a lot more circumspect."
Trump tried unsuccessfully to overturn his 2020 loss to Democratic President Joe Biden in a campaign that included more than 60 lawsuits and inspired his supporters' Jan. 6, 2021, attack on the U.S. Capitol.
Nearly all of the 2020 lawsuits filed by Trump and his allies were dismissed for lack of evidence and other issues.
Four of this year's lawsuits, filed in Michigan, Pennsylvania, Kansas and Texas, claim that a 2021 Biden administration initiative involving federal agencies in efforts to promote voter registration is a partisan effort to register voters likely to support Democrats.
Ken Blackwell, a former Ohio secretary of state who chairs the America First Policy Institute's Center for Election Integrity, said on the social platform X last month that the Biden administration was staging an "attempt to weaponize federal agencies into a leftwing election operation that opens the doors to non-citizen voting."
A 41-page complaint filed in Kansas federal court by Republican attorneys general from nine states makes only one reference to voting by undocumented immigrants, alleging that the Biden administration failed to examine the risks that "illegal aliens" may try to register to vote.
The RNC and North Carolina state Republican Party have twice sued that battleground state's election board, making allegations on non-citizen voting. The lawsuits allege the state registered nearly 225,000 voters, about 3% of its total, with insufficient documentation and had not removed from the rolls people who self-identified as non-citizens when reporting for jury duty.
The state is narrowly divided politically with two Republican senators, a Republican-controlled legislature, but a Democratic governor, Roy Cooper, and an evenly split delegation to the U.S. House of Representatives.
A state elections board spokesperson, Patrick Gannon, said it had complied with the jury duty requirement and identified nine registered voters who had claimed not to be citizens.
Those nine will be asked to cancel their registrations if their citizenship status cannot be confirmed, Gannon said, adding that the state cannot force them off the rolls this close to Election Day.
Gannon said the second lawsuit, over an allegedly flawed registration form, "vastly overstates any alleged problems."
In Arizona, a lawsuit filed by Trump-aligned advocacy group America First Legal is seeking to force counties to further investigate about 44,000 voters -- about 1% of the statewide total -- who were allowed to register without providing proof of citizenship.
That dispute revolves around the state's two-tiered voter-registration system, which requires proof of U.S. citizenship to vote in state elections, but does not mandate it in federal elections.
But even some longtime Arizona political operatives say non-citizen voting poses no danger to local elections.
"It's not happening," said Chuck Coughlin, a Phoenix-based political strategist who ended his lifelong Republican registration in 2017 and is now an independent. "It's a MAGA narrative intended to gaslight Republicans about election integrity."'''
 
    # send_data_b = "12345612345671234567123456712345678"
    send_data_a = "qwertyuioplkjhgfdsazxcvbnmqwertyuioplkjhgfdsazxcvbnm"
    send_data_c = "Hello World"
    try:
        while 1:
            choice = input()
            if choice == 's1':
                CanTp_Transmit(bus=bus, id= ID_TRANSMIT1, buffer=send_data_b, Transmit_Timeout= Transmit_Timeout, TX_DL = 8, is_fd= True)
                # CanTp_Transmit(bus=bus, id= ID_TRANSMIT2, buffer=send_data_a, Transmit_Timeout= Transmit_Timeout, TX_DL = 8, is_fd= True)
                # CanTp_Transmit(bus=bus, id= ID_TRANSMIT3, buffer=send_data_c, Transmit_Timeout= Transmit_Timeout, TX_DL = 8, is_fd= True)
            elif choice == "dc":
                new_BS = int(input("Enter new BS: "))
                new_STmin = int(input("Enter new STmin: "))
                new_WFT = int(input("Enter new WFT limit: "))
                dynamic_config(new_WFT= new_WFT, new_BS=new_BS, new_STmin=new_STmin)
            else:
                print("quit")
                break
        # Receive_State_Info.is_done = 1
    except KeyboardInterrupt:
        notifier.stop()
        bus.shutdown()