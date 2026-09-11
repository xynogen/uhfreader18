# UHFReader18 — UHF RFID Reader Protocol Reference

> Cleaned from UHFReader18 User's Manual V2.0

## Table of Contents

1. [Communication Interface](#1-communication-interface-specification)
2. [Protocol Description](#2-protocol-description)
3. [Data Block Format](#3-data-block-format)
4. [Command Summary](#4-operation-command-cmd-summary)
5. [Status Codes](#5-list-of-command-execution-result-status)
6. [Tag Error Codes](#6-tag-error-codes)
7. [Tag Memory](#7-tag-memory-and-issues-requiring-attention)
8. [Command Details](#8-detailed-description-of-operation-command)

---

## 1. COMMUNICATION INTERFACE SPECIFICATION

- **Interface:** RS232 or RS485
- **Baud rate:** 57600 bps (default)
- **Format:** 1 start bit, 8 data bits, 1 stop bit, no parity
- **Byte order:** LSbit first within each byte, LSByte first in multi-byte sequences

## 2. PROTOCOL DESCRIPTION

Communication is host-initiated: the host sends a command, the reader executes it and returns a response.

```
HOST  ──── Command Data Block ────►  READER
                                       │
                                       ▼ (executes)
HOST  ◄─── Response Data Block ───  READER
```

**Timing constraints:**

- Max gap between consecutive bytes in a data block: **15 ms** (or sync is lost)
- If the host receives data from the reader mid-command, stop sending and retry after 15 ms
- The reader processes **one command at a time** — commands sent during execution are lost
- Reader completes execution within the configured Inventory ScanTime (excludes host TX time)

## 3. DATA BLOCK FORMAT

### 3.1 Command Data Block

```
| Len | Adr | Cmd | Data[] | LSB-CRC16 | MSB-CRC16 |
```

| Field | Length | Description |
|-------|--------|-------------|
| `Len` | 1 | Data block length (not including itself). Range: `0x04`–`0x60`. Equals `len(Data[]) + 4`. |
| `Adr` | 1 | Reader address (`0x00`–`0xFE`). `0xFF` = broadcast. Default: `0x00`. |
| `Cmd` | 1 | Operation command code. |
| `Data[]` | Variable | Command parameters. Empty when `Len == 4`. |
| `LSB-CRC16` | 1 | CRC-16 checksum, least significant byte. |
| `MSB-CRC16` | 1 | CRC-16 checksum, most significant byte. |

### 3.2 Response Data Block

```
| Len | Adr | reCmd | Status | Data[] | LSB-CRC16 | MSB-CRC16 |
```

| Field | Length | Description |
|-------|--------|-------------|
| `Len` | 1 | Response length (not including itself). Equals `len(Data[]) + 5`. |
| `Adr` | 1 | Reader address (`0x00`–`0xFE`). |
| `reCmd` | 1 | Response command code. `0x00` if command unrecognized. |
| `Status` | 1 | Result status (see [Status Codes](#5-list-of-command-execution-result-status)). |
| `Data[]` | Variable | Response data. Empty when `Len == 5`. |
| `LSB-CRC16` | 1 | CRC-16 checksum, least significant byte. |
| `MSB-CRC16` | 1 | CRC-16 checksum, most significant byte. |

### 3.3 CRC-16 Calculation

CRC-16/CCITT reflected. Computed over all bytes starting from `Len`. Stored little-endian (LSB first).

```c
#define PRESET_VALUE 0xFFFF
#define POLYNOMIAL   0x8408

unsigned int uiCrc16Cal(unsigned char const *pucY, unsigned char ucX)
{
    unsigned char ucI, ucJ;
    unsigned short int uiCrcValue = PRESET_VALUE;

    for (ucI = 0; ucI < ucX; ucI++) {
        uiCrcValue = uiCrcValue ^ *(pucY + ucI);
        for (ucJ = 0; ucJ < 8; ucJ++) {
            if (uiCrcValue & 0x0001) {
                uiCrcValue = (uiCrcValue >> 1) ^ POLYNOMIAL;
            } else {
                uiCrcValue = (uiCrcValue >> 1);
            }
        }
    }
    return uiCrcValue;
}
```

## 4. OPERATION COMMAND (CMD) SUMMARY

4.1 EPC C1 G2 (ISO18000-6C) Commands

| # | Command | Code | Description |
|---|---------|------|-------------|
| 1 | Inventory | `0x01` | Inventory tags and get EPC values |
| 2 | Read Data | `0x02` | Read from Password, EPC, TID, or User memory (word-addressed) |
| 3 | Write Data | `0x03` | Write words to Reserved, EPC, TID, or User memory |
| 4 | Write EPC | `0x04` | Write EPC value to a random tag in field |
| 5 | Kill Tag | `0x05` | Permanently disable tag |
| 6 | Lock | `0x06` | Set memory bank read/write protection |
| 7 | Block Erase | `0x07` | Erase multiple words from memory |
| 8 | ReadProtect (with EPC) | `0x08` | Set read protection on specific tag (NXP G2X only) |
| 9 | ReadProtect (without EPC) | `0x09` | Set read protection on random tag in field (NXP G2X only) |
| 10 | Reset ReadProtect | `0x0A` | Remove read protection (NXP G2X only) |
| 11 | Check ReadProtect | `0x0B` | Check if tag is read-protected (NXP G2X only) |
| 12 | EAS Alarm | `0x0C` | Set/reset EAS status bit (NXP G2X only) |
| 13 | Check EAS Alarm | `0x0D` | Check EAS status (NXP G2X only) |
| 14 | Block Lock | `0x0E` | Permanently lock user memory rows (NXP G2X only) |
| 15 | Inventory (Single) | `0x0F` | Inventory single tag |
| 16 | Block Write | `0x10` | Write multiple words to memory |

4.2 18000-6B Commands

| # | Command | Code | Description |
|---|---------|------|-------------|
| 1 | Inventory Signal 6B | `0x50` | Inventory single 6B tag, get UID |
| 2 | Inventory Multiple 6B | `0x51` | Inventory multiple 6B tags by condition |
| 3 | Read Data 6B | `0x52` | Read bytes from address |
| 4 | Write Data 6B | `0x53` | Write bytes to address |
| 5 | Check Lock 6B | `0x54` | Check if byte is locked |
| 6 | Lock 6B | `0x55` | Lock a byte |

4.3 Reader-Defined Commands

| # | Command | Code | Description |
|---|---------|------|-------------|
| 1 | Get Reader Information | `0x21` | Get address, firmware version, protocol, power, frequency, scan time |
| 2 | Set Region | `0x22` | Set frequency band limits |
| 3 | Set Address | `0x24` | Set reader address (stored in EEPROM) |
| 4 | Set Scan Time | `0x25` | Set inventory scan time (`3–255` × 100ms) |
| 5 | Set Baud Rate | `0x28` | Change serial baud rate |
| 6 | Set Power | `0x2F` | Set RF output power |
| 7 | Acousto-optic Control | `0x33` | Control LED and buzzer |
| 8 | Set Wiegand | `0x34` | Configure Wiegand output |
| 9 | Set WorkMode | `0x35` | Set scan/trigger/answer mode |
| 10 | Get WorkMode | `0x36` | Get current work mode parameters |
| 11 | Set EAS Accuracy | `0x37` | Set EAS alarm accuracy (0–8) |
| 12 | Syris Response Offset | `0x38` | Set Syris485 response offset time |
| 13 | Trigger Offset | `0x3B` | Set trigger offset time |

## 5. LIST OF COMMAND EXECUTION RESULT STATUS

The response data block returns a `Status` byte indicating the result:

```
| Len | Adr | reCmd | Status | Data[] | CRC-16 |
```

| Status | Name | Description |
|--------|------|-------------|
| `0x00` | Success | Command executed successfully. `Data[]` contains result data. |
| `0x01` | Inventory Finished | Inventory complete — got some G2 tags' EPC before ScanTime finished. |
| `0x02` | Inventory Scan-Time Overflow | Did not get all G2 tags' EPC before ScanTime expired. Force quit. |
| `0x03` | More Data | Too many G2 tags — data split across multiple messages. |
| `0x04` | Reader Flash Full | Reader storage capacity exceeded during inventory. |
| `0x05` | Access Password Error | Wrong access password provided. |
| `0x09` | Kill Tag Error | Kill failed — wrong kill password or poor tag communication. |
| `0x0A` | Kill Password Can't Be Zero | Kill password must not be zero. |
| `0x0B` | Tag Not Support Command | Tag does not support this command. |
| `0x0C` | Access Password Can't Be Zero | NXP G2X: access password required for ReadProtect/EAS (can't be zero). |
| `0x0D` | Tag Is Protected | NXP G2X: tag is already read-protected, cannot set again. |
| `0x0E` | Tag Is Unprotected | NXP G2X: tag is not protected or doesn't support the command. |
| `0x10` | Some Bytes Locked, Write Fail | 6B tag: some target bytes are locked, write failed. |
| `0x11` | Cannot Lock | 6B tag: cannot be locked. |
| `0x12` | Already Locked | 6B tag: already locked, cannot lock again. |
| `0x13` | Save Fail | Parameter save failed. Can use before power cycle. |
| `0x14` | Cannot Adjust Power | Power cannot be adjusted. |
| `0x15` | 6B Inventory Finished | Got some 6B tags' UID before ScanTime finished. |
| `0x16` | 6B Scan-Time Overflow | Did not get all 6B tags' UID before ScanTime expired. |
| `0x17` | 6B More Data | Too many 6B tags — data split across multiple messages. |
| `0x18` | 6B Reader Flash Full | Reader storage capacity exceeded during 6B inventory. |
| `0x19` | Not Support Command or Pwd Zero | Tag doesn't support EAS, or access password is zero. |
| `0xF9` | Command Execute Error | Command execution error. |
| `0xFA` | Poor Communication | Tags present but communication with tag failed. |
| `0xFB` | No Tag Operable | No tag in the effective field. |
| `0xFC` | Tag Error Code | Tag returned an error code (extra byte `Err_code` in response). |
| `0xFD` | Command Length Wrong | Command operand length doesn't match expected. |
| `0xFE` | Illegal Command | Unrecognized command or CRC error. `reCmd` = `0x00`. |
| `0xFF` | Parameter Error | Invalid command parameter. |

## 6. TAG ERROR CODES

EPC C1G2 (ISO18000-6C) tag error codes:

| Error Code | Type | Name | Description |
|------------|------|------|-------------|
| `0x00` | Non-specific | Other | Catch-all for errors not covered by other codes |
| `0x03` | Error-specific | Memory Overrun | Memory location does not exist or EPC length field not supported |
| `0x04` | Error-specific | Memory Locked | Memory location is locked/perm-locked — not writeable or not readable |
| `0x0B` | Error-specific | Insufficient Power | Tag has insufficient power for the memory-write operation |
| `0x0F` | Non-specific | Non-specific | Tag does not support error-specific codes |

## 7. TAG MEMORY AND ISSUES REQUIRING ATTENTION

### A. EPC C1G2 Tag (G2 Tag)

Tag memory is logically separated into four banks:

| Bank | Name | Address Range | Description |
|------|------|---------------|-------------|
| 0 | **Reserved** (Password) | `00h`–`3Fh` | Kill password (`00h`–`1Fh`) + Access password (`20h`–`3Fh`) |
| 1 | **EPC** | `00h`+ | Stored CRC (`00h`–`0Fh`), Stored PC (`10h`–`1Fh`), EPC code (`20h`+), optional XPC (`210h`+) |
| 2 | **TID** | `00h`+ | ISO/IEC 15963 allocation class ID (`00h`–`07h`) + tag-specific identification |
| 3 | **User** | varies | Optional. Size varies by manufacturer (e.g., 0 words for Impinj, 28 words for Philips) |

**Write protection:** All four banks can be write-protected. Password bank can also be set unreadable.

### B. 18000-6B Tag

- Bytes 0–7: UID (read-only, cannot be rewritten)
- Bytes 8+: Read/write. Can be individually locked. **Once locked, cannot be rewritten or unlocked.**

## 8. DETAILED DESCRIPTION OF OPERATION COMMAND

### 8.1 COMMAND OVERVIEW

The reader supports three kinds of command, one kind is the ISO/IEC 18000-6 protocol command, another kind is reader-defined command, and also one kind is the transparent command. If the host input of the command is an unrecognized command, such as the command does not support, or CRC error in the command, then the return value is as follows:

| Len | Adr | reCmd | Status | CRC-16 | |
|--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x00 | 0xFE | LSB | MSB |

If the length of command operands doesn’t conform to the command request, the return value is as follows:

| Len | Adr | reCmd | Status | CRC-16 | |
|--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0xXX | 0xFD | LSB | MSB |

Two kinds of command reader cannot respond:

1. The reader’s address error.
2. The command is incomplete, namely the commandLenis longer than the actual command length.

### 8.2 EPC C1G2 COMMAND

#### 8.2.1 Inventory

The command function is used to inventory tags in the effective field and get their EPC or TID values. The reader executes anInventorycommand and gets tag’s EPC before any other operation. The user may accord need to establish this command the first biggest running time (Inventory scan time), before the command enquires. The reader completes command execution in inventory ScanTime (not including host sending data time) except inventory command after receiving host command and returns the results. The default value is 0x0A (corresponding to 10\*100ms=1s). The value range is 0x03\~0xFF (corresponding to 3\*100ms\~255\*100ms). In various environments, the actual inventory scan time may be 0\~75ms longer than the InventoryScanTime defined. If the inventory scan time establishes excessively short, possibly will inventory no tag appear in inventory scan time. Command: Data\[]

```
Len | Adr | Cmd | CRC-16 | AdrTID | LenTID
```

0xXX 0xXX 0x01 0xXX 0xXX LSB MSB

**Parameters:** AdrTID:One byte. It specifies the starting word address for the TID memory read. For example,AdrTID= 00h specifies the first 16-bit memory word,AdrTID= 01h specifies the second 16-bit memory word, etc.

LenTID:One byte. It specifies the number of 16-bit words to be read. The value is less then 16, otherwise, it returns the parameters error message. Notes:It will get tags’ EPC values when theAdrTIDandLenTIDvacant. Otherwise, get tags’ TID values. TID-inventory function is only available for reader with firmware version V2.36 and above.

**Response:**

```
Len | Adr | reCmd | Status | CRC-16 | Num | EPC | ID
```

0xXX 0xXX 0x01 0xXX 0xXX EPC-1, EPC-2, EPC-3… LSB MSB

**Parameters:**
**Status values:**
 Status Connect 0x01 Command over, and return inventoried tag’s EPC (TID). The reader does not get allG2tags’ EPC/TID before user-defined Inventory-ScanTime 0x02 overflows. Command force quit, and returns inventoried tags’ EPC (TID). 0x03 The reader executes anInventorycommand and gets manyG2tags’ EPC (TID). Data

can not be completed within in a message, and then send in multiple. The reader executes anInventorycommand and gets G2tags’ EPC (TID) too much, 0x04 more than the storage capacity of reader, and returns inventoried tags’ EPC (TID). Num: The number of tag detected.

EPC ID: Inventoried tag’s EPC (TID) data,EPC-1is the first tagEPC Len+EPCData(TID Len+TID Data), etc. The most significant word (EPC C1 G2 data in word units) of EPC is transmitted first and the most significant byte of word is transmitted first.EPC(TID)Lenis one byte.

#### 8.2.2 Read Data

The command is used to read part or all of a Tag’s Password, EPC, TID, or User memory. To the word as a unit, start to read data from the designated address. Command:

| Len | Adr | Cmd | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |
| 0xXX | 0xXX | 0x02 | —— | LSB | MSB |

**Data\[\]:**

| ENum | EPC | Mem | WordPtr | Num | Pwd | MaskAdr | MaskLen |
|--- |--- |--- |--- |--- |--- |--- |--- |
| 0xXX | Variable | 0xXX | 0xXX | 0xXX | 4Byte | 0xXX | 0xXX |

**Parameters:** ENum:EPC length，in word units. The length of EPC is less than 15 words, can be 0 or 15. Otherwise, it returns the parameters error message.

EPC: Be operated tag’s EPC number. EPC length according to the decision of the EPC number, EPC numbers in word units, and must be an integer number of lengths. High word first, the high byte of each word first. Requirement given here is a complete EPC number.

Mem: One byte. It specifies whether the Read accesses Password, EPC, TID, or User memory. 0x00: Password memory; 0x01: EPC memory; 0x02; TID memory; 0x03: User memory. Other values reserved. Other value when error occurred.

WordPtr:One byte. It specifies the starting word address for the memory read. For example,WordPtr= 00h specifies the first 16-bit memory word,WordPtr= 01h specifies the second 16-bit memory word, etc.

Num:One byte. It specifies the number of 16-bit words to be read. The value is less then 120, can not be 0. Otherwise, it returns the parameters error message.

Pwd:Four bytes, they are Access Password. The most significant word of Access Password is first, the most significant byte of word is first. The first bit of 32-bit access password is left, and the last bit of 32-bit access password is right. Only done the memory set to lock and the Tag’s Access Password is not zero, it needs right

Pwd. In other cases,Pwdcan be zero.

MaskAdr: One byte, it specifies the starting byte address for the memory mask. For example,MaskAdr = 0x00 specifies the firstEPCbytes,MaskAdr= 0x01 specifies the secondEPCbytes, etc.

MaskLen:One byte, it is the mask length. That a Tag compares against the memory location that begins at MaskAdr and ends MaskLen bytes later. MaskAdr + MaskLen must be less the length of ECP number. Otherwise, it returns the parameters error message.

> **Note:**That a tag compares against complete EPC number when theMaskAdrandMaskLenvacant.

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | | | |
|--- |--- |--- |--- |--- |--- |--- |--- |--- |
| 0xXX | 0xXX | 0x02 | 0x00 | Word1 | ， | Word2,… | LSB | MSB |

**Parameters:** Word1, Word2….:In word units, one word is two bytes. High byte is first.Word1is the word which reads from the start address,Word2is the word which reads from the second address, etc.

#### 8.2.3 Write Data

The command is used to write several words in a Tag’s Reserved, EPC, TID, or User memory. Command:

| Len | Adr | Cmd | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |
| 0xXX | 0xXX | 0x03 | —— | LSB | MSB |

**Data\[\]:**

| WNum | ENum | EPC | Mem | WordPtr | Wdt | Pwd | MaskAdr | MaskLen |
|--- |--- |--- |--- |--- |--- |--- |--- |--- |
| 0xXX | 0xXX | Variable | 0xXX | 0xXX | Variable | 4Byte | 0xXX | 0xXX |

**Parameters:** WNum:One byte. It specifies the number of 16-bit words to be written. The value can not be 0. Otherwise, it returns the parameters error message.

ENum:EPC length，in word units. The length of EPC is less than 15 words, can be 0 or 15. Otherwise, it returns the parameters error message.

EPC: Be operated tag’s EPC number. EPC length according to the decision of the EPC number, EPC numbers in word units, and must be an integer number of lengths. High word first, the high byte of each word first. Requirement given here is a complete EPC number.

Mem: One byte. It specifies whether the Write accesses Password, EPC, TID, or User memory. 0x00:

Password memory; 0x01: EPC memory; 0x02; TID memory; 0x03: User memory. Other values reserved. Other value when error occurred.

WordPtr:One byte. It specifies the starting word address for the memory write. For example,WordPtr= 00h specifies the first 16-bit memory word,WordPtr= 01h specifies the second 16-bit memory word, etc.

Wdt:Be written words. The most significant byte of each word is first.Wdtspecifies the array of the word to be written. For example, WordPtr equal 0x02, then the first word in Data write in the address 0x02 of designated Mem, the second word write in 0x03, etc.

Pwd:Four bytes, they are Access Password. The most significant word of Access Password is first, the most significant byte of word is first. The first bit of 32-bit access password is left, and the last bit of 32-bit access password is right. Only done the memory set to lock and the Access Password is not zero, it needsPwd. In other cases,Pwdcan be zero.

MaskAdr: One byte, it specifies the starting byte address for the memory mask. For example,MaskAdr = 0x00 specifies the firstEPCbytes,MaskAdr= 0x01 specifies the secondEPCbytes, etc. MaskLen:One byte, it is the mask length. That a Tag compares against the memory location that begins at MaskAdr and ends MaskLen bytes later. MaskAdr + MaskLen must be less the length of ECP number. Otherwise, it returns the parameters error message.

> **Note:**That a tag compares against complete EPC number when theMaskAdrandMaskLenvacant.

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x03 | 0x00 | —— | LSB | MSB |

#### 8.2.4 Write EPC

The command is used to write EPC number in a Tag’s EPC memory. Random write one tag in the effective field. Command: Data\[]

| Len | Adr | Cmd | CRC-16 | | | | |
|--- |--- |--- |--- |--- |--- |--- |--- |
| ENum | Pwd | WEPC | | | | | |
| 0xXX | 0xXX | 0x04 | 0xXX | 4Byte | Variable | LSB | MSB |

**Parameters:** ENum:One byte, it specifies the array of the word to be written EPC length，in word units. The length of EPC is not more than 15 words, can’t be 0. Otherwise, it returns the parameters error message.

Pwd:Four bytes, they are Access Password. The most significant word of Access Password is first, the most significant byte of word is first. The first bit of 32-bit access password is left, and the last bit of 32-bit access password is right. Only done the memory set to lock and the Access Password is not zero, it needsPwd. In other cases,Pwdcan be zero.

WEPC: Be written EPC value. WEPC is not more than 15 words, can’t be 0. Otherwise, it returns the parameters error message.

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x04 | 0x00 | —— | LSB | MSB |

#### 8.2.5 Kill Tag

The command is used to kill tag. After the tag killed, it never process command. Command:

| Len | Adr | Cmd | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |
| 0xXX | 0xXX | 0x05 | —— | LSB | MSB |

**Data\[\]:**

| ENum | EPC | Killpwd | MaskAdr | MaskLen |
|--- |--- |--- |--- |--- |
| 0xXX | Variable | 4Byte | 0xXX | 0xXX |

**Parameters:** ENum:EPC length，in word units. The length of EPC is less than 15 words, can be 0 or 15. Otherwise, it returns the parameters error message.

EPC: Be operated tag’s EPC number. EPC length according to the decision of the EPC number, EPC numbers in word units, and must be an integer number of lengths. High word first, the high byte of each word first. Requirement given here is a complete EPC number.

Killpwd: Four bytes, they are Kill Password. The most significant word of Kill Password is first, the most significant byte of word is first. The first bit of 32-bit Kill Password is left, and the last bit of 32-bit Kill Password is right. Tag’s whose Kill Password is zero do not execute a kill operation; if such a Tag receives a Killcommand it ignores the command and backscatters an error code

MaskAdr: One byte, it specifies the starting byte address for the memory mask. For example,MaskAdr = 0x00 specifies the firstEPCbytes,MaskAdr= 0x01 specifies the secondEPCbytes, etc.

MaskLen:One byte, it is the mask length. That a Tag compares against the memory location that begins at MaskAdr and ends MaskLen bytes later. MaskAdr + MaskLen must be less the length of ECP number. Otherwise, it returns the parameters error message.

> **Note:**That a tag compares against complete EPC number when theMaskAdrandMaskLenvacant.

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x05 | 0x00 | —— | LSB | MSB |

#### 8.2.6 Lock

TheLockcommand Lock reversibly or permanently locks a password or an entire EPC, TID, or User memory bank in a readable/writeable or unreadable/unwriteable state. Once tag’s password memory establishes to forever may be readable and writable or unreadable and unwriteable, then later cannot change its read-write protection again. Tag’s EPC memory, TID memory or user memory, if establishes to forever may be writeable or unwriteable, then later cannot change its read-write protection again. If sends the command to want forcefully to change the above several states, then the tag will return to the error code. When the tag’s memory established in a readable/writeable state, the command must give the Access Password, so tag’s Access Password is not zero.

**Command:**

| Len | Adr | Cmd | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |
| 0xXX | 0xXX | 0x06 | —— | LSB | MSB |

**Data\[\]:**

| ENum | EPC | Select | SetProtect | Pwd | MaskAdr | MaskLen |
|--- |--- |--- |--- |--- |--- |--- |
| 0xXX | Variable | 0xXX | 0xXX | 4Byte | 0xXX | 0xXX |

**Parameters:** ENum:EPC length，in word units. The length of EPC is less than 15 words, can be 0 or 15. Otherwise, it returns the parameters error message.

EPC: Be operated tag’s EPC number. EPC length according to the decision of the EPC number, EPC numbers in word units, and must be an integer number of lengths. High word first, the high byte of each word first. Requirement given here is a complete EPC number.

Select:One byte, defined as follows: 0x00: Control Kill Password protection setting. 0x01: Control Access password protection setting. 0x02: Control EPC memory protection setting. 0x03: Control TID memory protection setting. 0x04: Control User memory protection setting. Other value when error occurred.

SetProtect: When Select is 0x00 or 0x01,SetProtectmeans as follows: 0x00: readable and writeable from any state. 0x01: permanently readable and writeable. 0x02: readable and writeable from the secured state. 0x03: never readable and writeable When Select is 0x02, 0x03 or 0x04,SetProtectmeans as follows: 0x00: writeable from any state. 0x01: permanently writeable. 0x02: writeable from the secured state. 0x03: never writeable. Other value when error occurred.

Pwd:Four bytes, they are Access Password. The most significant word of Access Password is first, the most significant byte of word is first. The first bit of 32-bit access password is left, and the last bit of 32-bit access password is right.Pwdmust be right Access Password.

MaskAdr: One byte, it specifies the starting byte address for the memory mask. For example,MaskAdr = 0x00 specifies the firstEPCbytes,MaskAdr= 0x01 specifies the secondEPCbytes, etc.

MaskLen:One byte, it is the mask length. That a Tag compares against the memory location that begins at MaskAdr and ends MaskLen bytes later. MaskAdr + MaskLen must be less the length of ECP number. Otherwise, it returns the parameters error message.

> **Note:**That a tag compares against complete EPC number when theMaskAdrandMaskLenvacant.

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x06 | 0x00 | —— | LSB | MSB |

#### 8.2.7 BlockErase

The command is used to erase multiple words in a Tag’s Password, EPC, TID, or User memory. Command:

| Len | Adr | Cmd | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |
| 0xXX | 0xXX | 0x07 | —— | LSB | MSB |

**Data\[\]:**

| ENum | EPC | Mem | WordPtr | Num | Pwd | MaskAdr | MaskLen |
|--- |--- |--- |--- |--- |--- |--- |--- |
| 0xXX | Variable | 0xXX | 0xXX | 0xXX | 4Byte | 0xXX | 0xXX |

**Parameters:**

ENum:EPC length，in word units. The length of EPC is less than 15 words, can be 0 or 15. Otherwise, it returns the parameters error message. EPC: Be operated tag’s EPC number. EPC length according to the decision of the EPC number, EPC numbers in word units, and must be an integer number of lengths. High word first, the high byte of each word first. Requirement given here is a complete EPC number.

Mem: One byte. It specifies whether the Erase accesses Password, EPC, TID, or User memory. 0x00: Password memory; 0x01: EPC memory; 0x02; TID memory; 0x03: User memory. Other values reserved. Other value when error occurred.

WordPtr:One byte. It specifies the starting word address for the memory block erase. For example,WordPtr = 00h specifies the first 16-bit memory word, WordPtr = 01h specifies the second 16-bit memory word, etc. WordPtrmust be bigger than 0x00 when it erases EPC memory.

Num: One byte. It specifies the number of 16-bit words to be erased. If Num = 0x00, it returns the parameters error message.

Pwd:Four bytes, they are Access Password. The most significant word of Access Password is first, the most significant byte of word is first. The first bit of 32-bit access password is left, and the last bit of 32-bit access password is right. Only done the memory set to lock and the Access Password is not zero, it needsPwd. In other cases,Pwdcan be zero. MaskAdr: One byte, it specifies the starting byte address for the memory mask. For example,MaskAdr = 0x00 specifies the firstEPCbytes,MaskAdr= 0x01 specifies the secondEPCbytes, etc.

MaskLen:One byte, it is the mask length. That a Tag compares against the memory location that begins at MaskAdr and ends MaskLen bytes later. MaskAdr + MaskLen must be less the length of ECP number. Otherwise, it returns the parameters error message.

> **Note:**That a tag compares against complete EPC number when theMaskAdrandMaskLenvacant.

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x07 | 0x00 | —— | LSB | MSB |

#### 8.2.8 ReadProtect (With EPC)

The command is used to set designated tag read protection. After the tag protected, it never process command. Even if inventory tag, reader can not get the EPC number. The read protection can be removed by executing Reset ReadProtect. Only NXP's UCODE EPC G2X tags valid. Command:

| Len | Adr | Cmd | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |
| 0xXX | 0xXX | 0x08 | —— | LSB | MSB |

**Data\[\]:**

| ENum | EPC | Pwd | MaskAdr | MaskLen |
|--- |--- |--- |--- |--- |
| 0xXX | Variable | 4Byte | 0xXX | 0xXX |

**Parameters:** ENum:EPC length，in word units. The length of EPC is less than 15 words, can be 0 or 15. Otherwise, it returns the parameters error message.

EPC: Be operated tag’s EPC number. EPC length according to the decision of the EPC number, EPC numbers in word units, and must be an integer number of lengths. High word first, the high byte of each word first. Requirement given here is a complete EPC number.

Pwd:Four bytes, they are Access Password. The most significant word of Access Password is first, the most significant byte of word is first. The first bit of 32-bit access password is left, and the last bit of 32-bit access password is right. Tags’ Access Password can not be zero.

MaskAdr: One byte, it specifies the starting byte address for the memory mask. For example,MaskAdr = 0x00 specifies the firstEPCbytes,MaskAdr= 0x01 specifies the secondEPCbytes, etc.

MaskLen:One byte, it is the mask length. That a Tag compares against the memory location that begins at MaskAdr and ends MaskLen bytes later. MaskAdr + MaskLen must be less the length of ECP number. Otherwise, it returns the parameters error message.

> **Note:**That a tag compares against complete EPC number when theMaskAdrandMaskLenvacant.

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x08 | 0x00 | —— | LSB | MSB |

#### 8.2.9 ReadProtect (Without EPC)

The command is used to random set random one tag read protection in the effective field. The tag must be having the same access password. Only NXP's UCODE EPC G2X tags valid. Command: Data\[]

```
Len | Adr | Cmd | CRC-16 | Pwd
```

0x08 0xXX 0x09 4Byte LSB MSB **Parameters:** Pwd:Four bytes, they are Access Password. The most significant word of Access Password is first, the most significant byte of word is first. The first bit of 32-bit access password is left, and the last bit of 32-bit access password is right. Tags’ Access Password can not be zero.

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x09 | 0x00 | —— | LSB | MSB |

#### 8.2.10 Reset ReadProtect

The command is used to remove only one tag read protection in the effective field. The tag must be having the same access password. Only NXP's UCODE EPC G2X tags valid. Command: Data\[]

```
Len | Adr | Cmd | CRC-16 | Pwd
```

0x08 0xXX 0x0a 4Byte LSB MSB **Parameters:** Pwd:Four bytes, they are Access Password. The most significant word of Access Password is first, the most significant byte of word is first. The first bit of 32-bit access password is left, and the last bit of 32-bit access password is right.Pwdmust be right tag’s Access Password.

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x0a | 0x00 | —— | LSB | MSB |

> **Note:**If a tag does not support the command, is unlocked.

#### 8.2.11 Check ReadProtect

The command is used to check only one tag in the effective field, whether the tag is protected. It can not check the tag whether the tag support protection setting. Only NXP's UCODE EPC G2X tags valid. Command:

| Len | Adr | Cmd | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |
| 0x04 | 0xXX | 0x0b | —— | LSB | MSB |

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x06 | 0xXX | 0x0b | 0x00 | ReadPro | LSB | MSB |

**Parameters:** ReadPro Connect 0x00 Tag is protected. 0x01 Tag is unprotected. Notes:If a tag does not support the command, is unprotected.

#### 8.2.12 EAS Alarm

The function is used to set or reset the EAS status bit of designated tag. Only NXP's UCODE EPC G2X tags

valid. Command:

| Len | Adr | Cmd | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |
| 0xXX | 0xXX | 0x0c | —— | LSB | MSB |

**Data\[\]:**

| ENum | EPC | Pwd | EAS | MaskAdr | MaskLen |
|--- |--- |--- |--- |--- |--- |
| 0xXX | Variable | 4Byte | 0xXX | 0xXX | 0xXX |

**Parameters:** ENum:EPC length，in word units. The length of EPC is less than 15 words, can be 0 or 15. Otherwise, it returns the parameters error message.

EPC: Be operated tag’s EPC number. EPC length according to the decision of the EPC number, EPC numbers in word units, and must be an integer number of lengths. High word first, the high byte of each word first. Requirement given here is a complete EPC number.

Pwd:Four bytes, they are Access Password. The most significant word of Access Password is first, the most significant byte of word is first. The first bit of 32-bit access password is left, and the last bit of 32-bit access password is right. Tags’ Access Password can not be zero.

EAS:One byte. Bit0=0 means reset the EAS state, Bit0=1 means set the EAS state.Bit1\~Bit7 default 0.

MaskAdr: One byte, it specifies the starting byte address for the memory mask. For example,MaskAdr = 0x00 specifies the firstEPCbytes,MaskAdr= 0x01 specifies the secondEPCbytes, etc.

MaskLen:One byte, it is the mask length. That a Tag compares against the memory location that begins at MaskAdr and ends MaskLen bytes later. MaskAdr + MaskLen must be less the length of ECP number. Otherwise, it returns the parameters error message.

> **Note:**That a tag compares against complete EPC number when theMaskAdrandMaskLenvacant. Respond:

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x0c | 0x00 | —— | LSB | MSB |

#### 8.2.13 Check EAS Alarm

The function is used to check EAS status bit of any tag in the effective field. Only NXP's UCODE EPC G2X tags valid. Command:

| Len | Adr | Cmd | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |
| 0x04 | 0xXX | 0x0d | —— | LSB | MSB |

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x0d | 0x00 | —— | LSB | MSB |

It returns "no tag actionable" message when No EAS alarm

#### 8.2.14 User Block Lock

The command is used to permanently lock the designated data in designated tag’s user memory.Block Lock command supports an additional locking mechanism, which allows the locking of individual 32 bit blocks (rows) in the 224 bit User Memory. Once locked these locks cannot be unlocked. Only NXP's UCODE EPC G2X tags valid. Command:

| Len | Adr | Cmd | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |
| 0xXX | 0xXX | 0x0e | —— | LSB | MSB |

**Data\[\]:**

| ENum | EPC | pwd | WrdPointer | MaskAdr | MaskLen |
|--- |--- |--- |--- |--- |--- |
| 0xXX | Variable | 4Byte | 0xXX | 0xXX | 0xXX |

**Parameters:** ENum:EPC length，in word units. The length of EPC is less than 15 words, can be 0 or 15. Otherwise, it returns the parameters error message.

EPC: Be operated tag’s EPC number. EPC length according to the decision of the EPC number, EPC numbers in word units, and must be an integer number of lengths. High word first, the high byte of each word first. Requirement given here is a complete EPC number.

Pwd:Four bytes, they are Access Password. The most significant word of Access Password is first, the most significant byte of word is first. The first bit of 32-bit access password is left, and the last bit of 32-bit access password is right.Pwdmust be right tag’s Access Password.

WrdPointer:Each EEPROM row can be addressed by either of the two related WordPointers: Either of two WordPointers can address one single User Memory row WrdPointer User EEPROM row 0 or 1 0 2 or 3 1 4 or 5 2 6 or 7 3 8 or 9 4 10 or 11 5 12 or 13 6

MaskAdr: One byte, it specifies the starting byte address for the memory mask. For example,MaskAdr = 0x00 specifies the firstEPCbytes,MaskAdr= 0x01 specifies the secondEPCbytes, etc.

MaskLen:One byte, it is the mask length. That a Tag compares against the memory location that begins at MaskAdr and ends MaskLen bytes later. MaskAdr + MaskLen must be less the length of ECP number. Otherwise, it returns the parameters error message.

> **Note:**That a tag compares against complete EPC number when theMaskAdrandMaskLenvacant.

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x0e | 0x00 | —— | LSB | MSB |

#### 8.2.15 Inventory (Single)

**Command:**

| Len | Adr | Cmd | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |
| 0x04 | 0xXX | 0x0f | —— | LSB | MSB |

**Response:**

```
Len | Adr | reCmd | Status | CRC-16 | Num | EPC | ID
```

0xXX 0xXX 0x0f 0x01 0x01 EPC-1 LSB MSB

Num: The number of tag detected.

EPC ID: Inventoried tag’s EPC data,EPC-1is the first tagEPC Len+EPCdata. The most significant word (EPC C1 G2 data in word units) of EPC is transmitted first and the most significant byte of word is transmitted first.EPC Lenis one byte.

#### 8.2.16 Block Write

The command is used to write multiple words in a Tag’s Reserved, EPC, TID, or User memory. Command:

| Len | Adr | Cmd | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |
| 0xXX | 0xXX | 0x10 | —— | LSB | MSB |

**Data\[\]:**

| WNum | ENum | EPC | Mem | WordPtr | Wdt | Pwd | MaskAdr | MaskLen |
|--- |--- |--- |--- |--- |--- |--- |--- |--- |
| 0xXX | 0xXX | Variable | 0xXX | 0xXX | Variable | 4Byte | 0xXX | 0xXX |

**Parameters:**

WNum:One byte. It specifies the number of 16-bit words to be written. The value can not be 0. Otherwise, it returns the parameters error message.

ENum:EPC length，in word units. The length of EPC is less than 15 words, can be 0 or 15. Otherwise, it returns the parameters error message.

EPC: Be operated tag’s EPC number. EPC length according to the decision of the EPC number, EPC numbers in word units, and must be an integer number of lengths. High word first, the high byte of each word first. Requirement given here is a complete EPC number.

Mem: One byte. It specifies whether the Write accesses Password, EPC, TID, or User memory. 0x00: Password memory; 0x01: EPC memory; 0x02; TID memory; 0x03: User memory. Other values reserved. Other value when error occurred.

WordPtr:One byte. It specifies the starting word address for the memory write. For example,WordPtr= 00h specifies the first 16-bit memory word,WordPtr= 01h specifies the second 16-bit memory word, etc.

Wdt:Be written words. The most significant byte of each word is first.Wdtspecifies the array of the word to be written. For example, WordPtr equal 0x02, then the first word in Data write in the address 0x02 of designated Mem, the second word write in 0x03, etc.

Pwd:Four bytes, they are Access Password. The most significant word of Access Password is first, the most significant byte of word is first. The first bit of 32-bit access password is left, and the last bit of 32-bit access password is right. Only done the memory set to lock and the Access Password is not zero, it needsPwd. In other cases,Pwdcan be zero. MaskAdr: One byte, it specifies the starting byte address for the memory mask. For example,MaskAdr = 0x00 specifies the firstEPCbytes,MaskAdr= 0x01 specifies the secondEPCbytes, etc.

MaskLen:One byte, it is the mask length. That a Tag compares against the memory location that begins at MaskAdr and ends MaskLen bytes later. MaskAdr + MaskLen must be less the length of ECP number. Otherwise, it returns the parameters error message.

> **Note:**That a tag compares against complete EPC number when theMaskAdrandMaskLenvacant.

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x10 | 0x00 | —— | LSB | MSB |

### 8.3 18000-6B COMMAND

#### 8.3.1 Inventory Signal 6B

The command is used to Inventory only one tag in the effective field and get their ID values. If more than one tag in the effective field at the same time, reader may be get nothing. Command:

| Len | Adr | Cmd | CRC-16 | |
|--- |--- |--- |--- |--- |
| 0x04 | 0xXX | 0x50 | LSB | MSB |

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x0d | 0xXX | 0x50 | 0x00 | ID | LSB | MSB |

**Parameters:** ID:8 bytes, it is6Btag’s UID. The low byte is fist.

#### 8.3.2 Inventory Multiple 6B

The command is used to according to the given conditions Inventory tags in the effective field and get their ID values. Command: Data\[]

| Len | Adr | Cmd | CRC-16 | | | | | |
|--- |--- |--- |--- |--- |--- |--- |--- |--- |
| Condition | Address | Mask | Word\_data | | | | | |
| 0x0f | 0xXX | 0x51 | 0xXX | 0xXX | 0xXX | 8 Bytes | LSB | MSB |

**Parameters:** Condition:The condition of detecting tags. 0x00: equal condition. 0x01: unequal condition. 0x02: greater than condition. 0x03: lower than condition. Address:The tag’s start address to compare.

Mask:It pointed to the data is used to compare. Highest bit in the mask correspond with the far-left byte in the Condition Content. The corresponding bit in the mask is 1 to compare the bit in the Condition Content with the corresponding byte in the tag. The corresponding bit in the mask is 0, not compare.

Word\_data:8 bytes. It pointed to the array is used to compare.

**Response:**

| Len | Adr | reCmd | Status | Num | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |--- |
| 0xXX | 0xXX | 0x51 | 0xXX | 0xXX | UID1, UID2… | LSB | MSB |

**Parameters:**
**Status values:**

Status Connect 0x15 Command over, and return inventoried tag’s UID. The reader does not get all 6B tags’ UID before user-defined Inventory-ScanTime 0x16 overflows. Command force quit, and returns inventoried tags’ UID. The reader executes anInventorycommand and gets many6Btags’ UID. Data can not 0x17 be completed within in a message, and then send in multiple. The reader executes an Inventory command and gets 6B tags’ UID too much, more 0x18 than the storage capacity of reader, and returns inventoried tags’ UID. Num: The number of tag detected. Data \[]:UID. Each UID length is 8 bytes. The least significant byte of UID is transmitted first.

#### 8.3.3 Read Data 6B

The command is used to start to read several bytes from the designated address. Command： Data\[]

| Len | Adr | Cmd | CRC-16 | | | | |
|--- |--- |--- |--- |--- |--- |--- |--- |
| Address | ID | Num | | | | | |
| 0x0e | 0xXX | 0x52 | 0xXX | 8 Bytes | 0xXX | LSB | MSB |

**Parameters:** Address:The tag’s start byte address to read. The range is 0\~223. Otherwise, it returns the parameters error message.

Num:In byte units. It specifies the number of 8-bit bytes to be read. The value range is 1\~32, andAddress+ Nummust be less than 224. Otherwise, it returns the parameters error message.

ID:8 bytes, it is6Btag’s UID. The low byte is fist.

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x52 | 0x00 | Data | LSB | MSB |

Data:It is read data, the low byte is fist.

#### 8.3.4 Write Data 6B

The command is used to start to write several bytes from the designated address. Command: Data\[]

| Len | Adr | Cmd | CRC-16 | | | | |
|--- |--- |--- |--- |--- |--- |--- |--- |
| Address | ID | Wdata | | | | | |
| 0xXX | 0xXX | 0x53 | 0xXX | 8 Bytes | Variable | LSB | MSB |

**Parameters:** Address:The tag’s start byte address to write. The range is 8\~223. Otherwise, it returns the parameters error message.

ID:8 bytes, it is6Btag’s UID. The low byte is fist.

Wdata: It pointed to the array to write, range is 1\~32. If Address + WriteDataLen greater than 224, or Wdatagreater than 32 or is zero, reader will return parameter error message. The high bytes ofWdatawrite in the low address in tag.

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x53 | 0x00 | Data | LSB | MSB |

#### 8.3.5 Check Lock 6B

The command is used to check whether the designated byte is locked. Command: Data\[]

```
Len | Adr | Cmd | CRC-16 | Address | ID
```

0x0d 0xXX 0x54 0xXX 8 Bytes LSB MSB

**Parameters:** Address:The tag’s byte address to check lock. The range is 0\~223. Otherwise, it returns the parameters error message.

ID:8 bytes, it is6Btag’s UID. The low byte is fist.

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x06 | 0xXX | 0x54 | 0x00 | LockState | LSB | MSB |

LockState: 0x00: Unlocked 0x01: locked

#### 8.3.6 Lock 6B

The command is used to lock the designated byte. Command: Data\[]

```
Len | Adr | Cmd | CRC-16 | Address | ID
```

0x0d 0xXX 0x55 0xXX 8 Bytes LSB MSB

**Parameters:** Address: The tag’s byte address to lock. The range is 8\~223. Otherwise, it returns the parameters error message.

ID:8 bytes, it is6Btag’s UID. The low byte is fist.

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x55 | 0x00 | —— | LSB | MSB |

### 8.4 READ-DEFINED COMMAND

#### 8.4.1 Get Reader Information

The host sends this command to get the reader’s information including reader’s address (Adr), firmware version, reader’s type (Type), supported protocol (Tr\_Type), reader power, work frequency, and InventoryScanTime value. Command:

| Len | Adr | Cmd | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |
| 0x04 | 0xXX | 0x21 | —— | LSB | MSB |

**Response:**

```
Len | Adr | reCmd | Status | Data\[] | CRC-16 | Version，Type，Tr\_Type，DMaxFr
```

0x0d 0xXX 0x21 0x00 LSB MSB e，DMinFre，Power，Scntm **Parameters:** Length(Byte Parameter Connect) The first byte is version number; the second byte is sub-version Version 2 number.

Type 1 The reader type byte. 0x09 lines on UHFREADER18 One byte supported protocol information. Bit1 is 1 for18000-6C Tr\_Type 1 protocol; Bit0 is 1 for 18000-6B protocol. Bit7-Bit6 indicates Frequency Band and Bit5-Bit0 indicates the DMaxFre 1 reader current maximum frequency. Bit7-Bit6 indicates Frequency Band and Bit5-Bit0 indicates the DMinFre 1 reader current minimum frequency. The output power of reader. Range is 0 to 30, when Power is 0xFF, Power 1 it means the output power of reader unknown. Inventory Scan Time, the value of time limit for inventory Scntm 1 command. Frequency Band:

| MaxFre(Bit7) | MaxFre(Bit6) | MinFre(Bit7) | MinFre(Bit6) | FreqBand |
|--- |--- |--- |--- |--- |
| 0 | 0 | 0 | 0 | User band |
| 0 | 0 | 0 | 1 | Chinese band2 |
| 0 | 0 | 1 | 0 | US band |
| 0 | 0 | 1 | 1 | Korean band |

| 0 | 1 | 0 | 0 | RFU |
|--- |--- |--- |--- |--- |
| 0 | 1 | 0 | 1 | RFU |
| … | … | … | … | … |
| 1 | 1 | 1 | 1 | RFU |

#### 8.4.2 Set Region

The host sends this command to change the current region of the reader. The value is stored in the reader’s inner EEPROM and is nonvolatile after reader powered off. Command: Data\[]

```
Len | Adr | Cmd | CRC-16 | MaxFre | MinFre
```

0x06 0xXX 0x22 0xXX 0xXX LSB MSB **Parameters:** MaxFre:One byte, Bit7-Bit6 indicates Frequency Band and Bit5-Bit0 indicates the reader current maximum frequency.

MinFre:One byte, Bit7-Bit6 indicates Frequency Band and Bit5-Bit0 indicates the reader current minimum frequency (maximum frequency>=minimum frequency).

Frequency Band:

| MaxFre(Bit7) | MaxFre(Bit6) | MinFre(Bit7) | MinFre(Bit6) | FreqBand |
|--- |--- |--- |--- |--- |
| 0 | 0 | 0 | 0 | User band |
| 0 | 0 | 0 | 1 | Chinese band2 |
| 0 | 0 | 1 | 0 | US band |
| 0 | 0 | 1 | 1 | Korean band |
| 0 | 1 | 0 | 0 | RFU |
| 0 | 1 | 0 | 1 | RFU |
| … | … | … | … | … |
| 1 | 1 | 1 | 1 | RFU |

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x22 | 0x00 | —— | LSB | MSB |

Various frequency bands formula: User band: Fs = 902.6 + N \* 0.4 (MHz), N∈\[0, 62]. Chinese band2: Fs = 920.125 + N \* 0.25 (MHz), N∈\[0, 19]. US band: Fs = 902.75 + N \* 0.5 (MHz), N∈\[0, 49]. Korean band: Fs = 917.1 + N \* 0.2 (MHz), N∈\[0, 31].

#### 8.4.3 Set Address

The host sends this command to change the address (Adr) of the reader. The address data is stored in the reader’s inner EEPROM and is nonvolatile after reader powered off. The default value ofAdris 0x00. The range of Adr is 0x00\~0xFE. When the host tries to write 0xFF to Adr, the reader will set the value to 0x00 automatically. Command: Data\[]

```
Len | Adr | Cmd | CRC-16 | Address
```

0x05 0xXX 0x24 0xXX LSB MSB

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x24 | 0x00 | —— | LSB | MSB |

> **Note:** TheAdris old address, not new address.

#### 8.4.4 Set Scan Time

The host sends this command to change the value of InventoryScanTime of the reader. The value is stored in the reader’s inner EEPROM and is nonvolatile after reader powered off. Command: Data\[]

```
Len | Adr | Cmd | CRC-16 | Scantime
```

0x05 0xXX 0x25 0xXX LSB MSB **Parameters:** Scantime: Inventory Scan Time. The default value is 0x0A (corresponding to 10\*100ms=1s). The value range is 0x03\~0xFF (corresponding to 3\*100ms\~255\*100ms). When the host tries to set value 0x00\~0x02 to InventoryScanTime, the reader will set it to 0x0A automatically. In various environments, the actual inventory scan time may be 0\~75ms longer than the InventoryScanTime defined.

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x25 | 0x00 | —— | LSB | MSB |

#### 8.4.5 Set Band Rate

The host sends this command to change the value of band rate of the reader. The value is stored in the reader’s inner EEPROM and is nonvolatile after reader powered off. Command: Data\[]

```
Len | Adr | Cmd | CRC-16 | BaudRate
```

0x05 0xXX 0x28 0xXX LSB MSB **Parameters:** BaudRate:The serial port baud rate default value is 57600 bps. Defined as follows:

BaudRate Bps 0 9600bps 1 19200 bps 2 38400 bps 5 57600 bps 6 115200 bps

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x28 | 0x00 | —— | LSB | MSB |

> **Note:**The response of the baud rate for the original baud rate, and next command uses the new band rate.

#### 8.4.6 Set Power

The host sends this command to change the power of the reader. The value is stored in the reader’s inner EEPROM and is nonvolatile after reader powered off. Command: Data\[]

```
Len | Adr | Cmd | CRC-16 | Pwr
```

0x05 0xXX 0x2F 0xXX LSB MSB **Parameters:**

Pwr:New power. The default value is 30(about 30dBm), it range is 0\~30.

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x2F | 0x00 | —— | LSB | MSB |

#### 8.4.7 Acousto-optic Control

The host sends this command to control the LED lights flash and buzzer tweet. Command:

| Len | Adr | Cmd | CRC-16 | | | | |
|--- |--- |--- |--- |--- |--- |--- |--- |
| ActiveT | SilentT | Times | | | | | |
| 0x07 | 0xXX | 0x33 | 0xXX | 0xXX | 0xXX | LSB | MSB |

**Parameters:** ActiveT:LED flash and buzzer tweet time. (ActiveT\*50ms), the default value is 0. 0<=ActiveT<=255.

SilentT:The LED and the buzzer silent time (SilentT\*50ms), the default value is0. 0<=SilentT<=255.

Times:LED flash and buzzer tweet times (0<=Times<=255), the default value is0.

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x33 | 0x00 | —— | LSB | MSB |

#### 8.4.8 Set Wiegand

The host sends this command to change Wiegand parameter of the reader. The value is stored in the reader’s inner EEPROM and is nonvolatile after reader powered off. Command:

| Len | Adr | Cmd | Wg\_mo | Wg\_Data\_I | Wg\_Pulse\_Wi | Wg\_Pulse\_In | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |--- |--- |
| de | nteval | dth | teval | | | | | |
| 0x08 | 0xXX | 0x34 | 0xXX | 0xXX | 0xXX | 0xXX | LSB | MSB |

**Parameters:** Wg\_mode:Bit0: Select Wiegand format interface. =0 Wiegand 26bits format interface. =1 Wiegand 34bits format interface. Bit1: High-bit first or Low-bit first. =0 High-bit first. =1 Low-bit first. Bit2\~Bit7: RFU. Default value is zero.

Wg\_Data\_Inteval:Sending Data Delay (0 \~255)\*10ms, the default value is 30.

Wg\_Pulse\_Width:Data pulse width (1 \~255)\*10us, the default value is 10.

Wg\_Pulse\_Inteval:Data pulse interval width (1 \~255)\*100us, the default value is 15.

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x34 | 0x00 | —— | LSB | MSB |

#### 8.4.9 Set WorkMode

The host sends this command to set the reader’s in Scan Mode or Trigger Mode. The host can also use this

command to define the reader’s output data content and format. In Scan Mode or Trigger Mode, the reader can still accept commands from the host. But it will only respond to reader-defined commands. Other commands can not be executed when the reader in Scan Mode or Trigger Mode. Command:

```
Len | Adr | Cmd | CRC-16 | Parameter
```

0x0a 0xXX 0x35 6Bytes LSB MSB

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x35 | 0x00 | —— | LSB | MSB |

Note: Scan Mode configuration wordsParameterwill be stored in reader’s EEPROM and be effective until changed explicitly. Defined as follows:

| Byte1 | Byte2 | Byte3 | Byte4 | Byte5 | Byte6 |
|--- |--- |--- |--- |--- |--- |
| Read\_mode | Mode\_state | Mem\_Inven | First\_Adr | Word\_Num | Tag\_Time |

**Parameters:** Read\_mode:

| Bit1 | Bit0 | Work Mode |
|--- |--- |--- |
| 0 | 0 | Answer Mode |
| 0 | 1 | Scan Mode |
| 1 | 0 | Trigger Mode(Low) |
| 1 | 1 | Trigger Mode(High) |

Bit2\~Bit7: RFU. Default value is zero. Notes:Answer mode, the following parameter is invalid.

Mode\_state:Bit0: Protocol bit. =0 the reader support 18000-6C protocol. =1 the reader support 18000-6B protocol. Bit1: Output mode bit. =0 Wiegand output. =1 RS232/RS485 output. Bit2: Beep Enable. =0 on =1 off Bit3: Wiegand output, 18000-6C protocol.First\_Adris byte address or word address. =0 word address. =1 bytes address. Bit4: Syris485 Enable. It is invalid when Bit1 is zero. =0 Common 485

\=1 Syris 485 When Bit4 = 1: Validity: 18000-6C protocol: Read accesses Password, EPC, TID, User memory, Inventory Single. 18000-6B protocol: validity.

Bit5\~Bit7: RFU. Default value is zero.

Mem\_Inven:It is valid when the reader supports 18000-6C protocol. It specifies whether the Read accesses

```
Password, EPC, TID, User memory, Inventory multiple, Inventory Single, EAS Alarm. 0x00: Password memory;
0x01: EPC memory; 0x02; TID memory; 0x03: User memory; 0x04 Inventory multiple; 0x05 Inventory Single;
```

0x06: EAS Alarm. Otherwise, it returns the parameters error message.

First\_Adr:It specifies the starting data address for the memory read. Support 18000-6C:First\_Adr= 0x00 specifies the first 16-bit memory word,First\_Adr= 0x01 specifies the second 16-bit memory word, etc. Support 18000-6B:First\_Adr= 0x00 specifies the first 8-bit memory byte,First\_Adr= 0x01 specifies the second 8-bit memory byte, etc.

Word\_Num:Only RS232 RS232/RS485 output, it is valid. It specifies the number of word for the memory read. The value range is 1\~32. Syris 485 Mode, the value range is 1\~4.

Tag\_Time:Read Single Tag Delay (0 \~255)\*1s. The default value is zero. Validity: 18000-6C protocol: Read accesses Password, EPC, TID, User memory, Inventory Single. 18000-6B protocol: validity. Output Format Connect In The Scan Mode Or Trigger Mode:

RS232/RS485, serial output format is as follows: Notes: RS232/RS485 serial output mode, these must be no tag in the effective field when set reader parameter.

1.18000-6C Protocol, Mem\_Inven is 0x00\~0x03:

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | | | |
|--- |--- |--- |--- |--- |--- |--- |--- |--- |
| 0xXX | 0xXX | 0xee | 0x00 | Word1 | ， | Word2,… | LSB | MSB |

**Parameters:** Word1, Word2….:In word units, one word is two bytes. High-byte is first.Word1is the word which reads from the start address,Word2is the word which reads from the second address, etc.

2.18000-6C Protocol, Mem\_Inven is 0x04 or 0x05:

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0xXX | 0xXX | 0xee | 0x00 | EPC ID | LSB | MSB |

**Parameters:** EPC ID: G2 tag’s ECP, The most significant word (EPC C1 G2 data in word units) of EPC is transmitted first and the most significant byte of word is transmitted first.

3.18000-6C Protocol, Mem\_Inven is 0x06:

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0xXX | 0xXX | 0xee | 0xee | —— | LSB | MSB |

4.18000-6B Protocol:

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | | | |
|--- |--- |--- |--- |--- |--- |--- |--- |--- |
| 0xXX | 0xXX | 0xee | 0x00 | Word1 | ， | Word2,… | LSB | MSB |

**Parameters:** Data \[]: 6Btag’s UID. UID length is 8 bytes. The least significant byte of UID is transmitted first.

#### 8.4.10 Get WorkMode

The host sends this command to get the reader’s information including reader’s Wiegand parameter, WorkMode parameter. Command:

| Len | Adr | Cmd | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |
| 0x04 | 0xXX | 0x36 | —— | LSB | MSB |

**Response:**

```
Len | Adr | reCmd | Status | Data\[] | CRC-16
```

Wg\_mode，Wg\_Data\_Inteval，Wg\_Puls e\_Width，Wg\_Pulse\_Inteval，Read\_mo

0x11 0xXX 0x36 0x00 de，Mode\_state，Mem\_Inven，First\_A LSB MSB dr，Word\_Num，Tag\_Time，accuracy

```
，OffsetTime
```

**Parameters:** Wg\_mode, Wg\_Data\_Inteval, Wg\_Pulse\_Width, Wg\_Pulse\_Inteval:Wiegand parameters.

Read\_mode, Mode\_state, Mem\_Inven, First\_Adr, Word\_Num, Tag\_Time:Work Mode parameters.

Accuracy:EAS Alarm accuracy.

OffsetTime:Syris485 response offset time.

#### 8.4.11 SetEasAccuracy

The host sends this command to set EAS Alarm Accuracy. Command:

```
Len | Adr | Cmd | CRC-16 | Accuracy
```

0x05 0xXX 0x37 0xXX LSB MSB

Accuracy:EAS Alarm Accuracy. The default value is 8, it range is 0\~8.

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x37 | 0x00 | —— | LSB | MSB |

#### 8.4.12 Syris Response Offset

The host sends this command to set Syris485 response offset time. Command:

```
Len | Adr | Cmd | CRC-16 | OffsetTime
```

0x05 0xXX 0x38 0xXX LSB MSB

OffsetTime:Syris485 response offset time (0 \~100)\*1ms, the default value is 0.

**Response:**

| Len | Adr | reCmd | Status | Data\[] | CRC-16 | |
|--- |--- |--- |--- |--- |--- |--- |
| 0x05 | 0xXX | 0x38 | 0x00 | —— | LSB | MSB |

#### 8.4.13 Trigger Offset

The host sends this command to set Trigger offset time. This function is only available for reader with firmware version V2.36 and above. Command:

```
Len | Adr | Cmd | CRC-16 | TriggerTime
```

0x05 0xXX 0x3b 0xXX LSB MSB

TriggerTime:Trigger offset time (0 \~254)\*1s, the default value is 0. WhenTriggerTimeis 255, means get the current trigger offset time.

**Response:**

```
Len | Adr | reCmd | Status | Data\[] | CRC-16
```

0x05 0xXX 0x3b 0x00 TriggerTime LSB MSB

TriggerTime：CurrentTrigger offset time (0 \~254)\*1s.
