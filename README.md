# CAN Transport Protocol (CAN-TP) Simulation using Python CAN

## 1. Description

This project simulates CAN Transport Protocol (CAN-TP) operations using the `python-can` library. It includes three scripts for different types of simulations:

- **`cantp_valuecan4_v2.py`**: The recommended script for CAN-TP simulation using a physical CAN device (e.g., ValueCAN).
- **`cantp_valuecan4.py`**: An older version of the CAN-TP simulation with CAN devices, still functional but superseded by the `v2` version.
- **`cantp.py`**: Simulates CAN-TP operations over a virtual CAN bus, allowing for testing without any physical CAN hardware.

## 2. Features

- **Single and Multi-frame Message Transmission**: Simulates the transmission and reception of both single-frame and multi-frame messages.
- **Timeout Handling**: Simulates timeouts for both message transmission and reception, including detailed control over timeout values.
- **Multiple Connection Simulation**: Supports multiple CAN-TP connections, enabling simultaneous transmission and reception for different IDs.
- **Frame Error Handling**: Simulates various frame-related errors, including Sequence Number (SN) errors, Single Frame Data Length (SF_DL) errors, and more.
- **Support for CAN FD and Classic CAN**: Works with both CAN FD and classic CAN communication protocols.

## 3. Usage Instructions

### 3.1 `cantp.py`

To simulate multiple connections, modify the following code snippet to transmit data for different IDs:

```python
CanTp_Transmit(bus=bus, id=ID_TRANSMIT1, buffer=send_data_b, Transmit_Timeout=Transmit_Timeout, TX_DL=8, is_fd=True)
CanTp_Transmit(bus=bus, id=ID_TRANSMIT2, buffer=send_data_a, Transmit_Timeout=Transmit_Timeout, TX_DL=8, is_fd=True)
CanTp_Transmit(bus=bus, id=ID_TRANSMIT3, buffer=send_data_c, Transmit_Timeout=Transmit_Timeout, TX_DL=8, is_fd=True)
````
You can add new connections by extending the transmission and reception dictionaries. For example:

```python
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
```

Due to the high latency when using the virtual bus, use the following timeout values:
```
Receive_Timeout = RcvTimeout(4, 4, 8)
Transmit_Timeout = TsmTimeout(4, 8, 8)
```

Look for the following comments in the code to simulate timeout scenarios: **`AST`**, **`ART`**, **`BRT`** 

To start the transmission, press **`s1`**. To change values such as STmin, BS, and WFTmax, press **`dc`** .

### 3.1 `cantp_valuecan4_v2.py`
This script works similarly to cantp_valuecan4.py but with improvements and optimizations. To run the simulation on a physical CAN bus, use the following timeout values:
```
Receive_Timeout = RcvTimeout(0.2, 0.2, 0.4)
Transmit_Timeout = TsmTimeout(0.2, 0.4, 0.4)
```