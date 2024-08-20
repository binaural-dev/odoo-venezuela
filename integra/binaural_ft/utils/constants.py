# -*- coding: utf-8 -*-

""" ESC/POS Commands (Constants) """

SEPARATOR = b"------------------------------------------------"
SEPARATOR_SMALL = b"----------------------------------------------------------------"

# Control characters
ESC = b"\x1b"

# Feed control sequences
CTL_LF = b"\x0a"  # Print and line feed
CTL_FF = b"\x0c"  # Form feed
CTL_CR = b"\x0d"  # Carriage return
CTL_HT = b"\x09"  # Horizontal tab
CTL_VT = b"\x0b"  # Vertical tab

# RT Status commands
DLE_EOT_PRINTER = b"\x10\x04\x01"  # Transmit printer status
DLE_EOT_OFFLINE = b"\x10\x04\x02"
DLE_EOT_ERROR = b"\x10\x04\x03"
DLE_EOT_PAPER = b"\x10\x04\x04"

# Printer hardware
HW_INIT = b"\x1b\x40"  # Clear data in buffer and reset modes
HW_SELECT = b"\x1b\x3d\x01"  # Printer select
HW_RESET = b"\x1b\x3f\x0a\x00"  # Reset printer hardware
# Paper
PAPER_FULL_CUT = b"\x1d\x56\x00"  # Full cut paper
PAPER_PART_CUT = b"\x1d\x56\x01"  # Partial cut paper
# Text format
TXT_NORMAL = b"\x1b\x21\x00"  # Normal text
TXT_2HEIGHT = b"\x1b\x21\x10"  # Double height text
TXT_2WIDTH = b"\x1b\x21\x20"  # Double width text
TXT_DOUBLE = b"\x1b\x21\x30"  # Double height & Width
TXT_UNDERL_OFF = b"\x1b\x2d\x00"  # Underline font OFF
TXT_UNDERL_ON = b"\x1b\x2d\x01"  # Underline font 1-dot ON
TXT_UNDERL2_ON = b"\x1b\x2d\x02"  # Underline font 2-dot ON
TXT_BOLD_OFF = b"\x1b\x45\x00"  # Bold font OFF
TXT_BOLD_ON = b"\x1b\x45\x01"  # Bold font ON
TXT_FONT_A = b"\x1b\x4d\x00"  # Font type A
TXT_FONT_B = b"\x1b\x4d\x01"  # Font type B
TXT_ALIGN_LT = b"\x1b\x61\x00"  # Left justification
TXT_ALIGN_CT = b"\x1b\x61\x01"  # Centering
TXT_ALIGN_RT = b"\x1b\x61\x02"  # Right justification
TXT_ITALICS = b"\x1b\x34\x01"
TXT_COLOR_BLACK = b"\x1b\x72\x00"  # Default Color
TXT_COLOR_RED = b"\x1b\x72\x01"  # Alternative Color ( Usually Red )

# Text Encoding

TXT_ENC_PC437 = b"\x1b\x74\x00"  # PC437 USA
TXT_ENC_KATAKANA = b"\x1b\x74\x01"  # KATAKANA (JAPAN)
TXT_ENC_PC850 = b"\x1b\x74\x02"  # PC850 Multilingual
TXT_ENC_PC860 = b"\x1b\x74\x03"  # PC860 Portuguese
TXT_ENC_PC863 = b"\x1b\x74\x04"  # PC863 Canadian-French
TXT_ENC_PC865 = b"\x1b\x74\x05"  # PC865 Nordic
TXT_ENC_KANJI6 = b"\x1b\x74\x06"  # One-pass Kanji, Hiragana
TXT_ENC_KANJI7 = b"\x1b\x74\x07"  # One-pass Kanji
TXT_ENC_KANJI8 = b"\x1b\x74\x08"  # One-pass Kanji
TXT_ENC_PC851 = b"\x1b\x74\x0b"  # PC851 Greek
TXT_ENC_PC853 = b"\x1b\x74\x0c"  # PC853 Turkish
TXT_ENC_PC857 = b"\x1b\x74\x0d"  # PC857 Turkish
TXT_ENC_PC737 = b"\x1b\x74\x0e"  # PC737 Greek
TXT_ENC_8859_7 = b"\x1b\x74\x0f"  # ISO8859-7 Greek
TXT_ENC_WPC1252 = b"\x1b\x74\x10"  # WPC1252
TXT_ENC_PC866 = b"\x1b\x74\x11"  # PC866 Cyrillic #2
TXT_ENC_PC852 = b"\x1b\x74\x12"  # PC852 Latin2
TXT_ENC_PC858 = b"\x1b\x74\x13"  # PC858 Euro
TXT_ENC_KU42 = b"\x1b\x74\x14"  # KU42 Thai
TXT_ENC_TIS11 = b"\x1b\x74\x15"  # TIS11 Thai
TXT_ENC_TIS18 = b"\x1b\x74\x1a"  # TIS18 Thai
TXT_ENC_TCVN3 = b"\x1b\x74\x1e"  # TCVN3 Vietnamese
TXT_ENC_TCVN3B = b"\x1b\x74\x1f"  # TCVN3 Vietnamese
TXT_ENC_PC720 = b"\x1b\x74\x20"  # PC720 Arabic
TXT_ENC_WPC775 = b"\x1b\x74\x21"  # WPC775 Baltic Rim
TXT_ENC_PC855 = b"\x1b\x74\x22"  # PC855 Cyrillic
TXT_ENC_PC861 = b"\x1b\x74\x23"  # PC861 Icelandic
TXT_ENC_PC862 = b"\x1b\x74\x24"  # PC862 Hebrew
TXT_ENC_PC864 = b"\x1b\x74\x25"  # PC864 Arabic
TXT_ENC_PC869 = b"\x1b\x74\x26"  # PC869 Greek
TXT_ENC_PC936 = b"\x1C\x21\x00"  # PC936 GBK(Guobiao Kuozhan)
TXT_ENC_8859_2 = b"\x1b\x74\x27"  # ISO8859-2 Latin2
TXT_ENC_8859_9 = b"\x1b\x74\x28"  # ISO8859-2 Latin9
TXT_ENC_PC1098 = b"\x1b\x74\x29"  # PC1098 Farsi
TXT_ENC_PC1118 = b"\x1b\x74\x2a"  # PC1118 Lithuanian
TXT_ENC_PC1119 = b"\x1b\x74\x2b"  # PC1119 Lithuanian
TXT_ENC_PC1125 = b"\x1b\x74\x2c"  # PC1125 Ukrainian
TXT_ENC_WPC1250 = b"\x1b\x74\x2d"  # WPC1250 Latin2
TXT_ENC_WPC1251 = b"\x1b\x74\x2e"  # WPC1251 Cyrillic
TXT_ENC_WPC1253 = b"\x1b\x74\x2f"  # WPC1253 Greek
TXT_ENC_WPC1254 = b"\x1b\x74\x30"  # WPC1254 Turkish
TXT_ENC_WPC1255 = b"\x1b\x74\x31"  # WPC1255 Hebrew
TXT_ENC_WPC1256 = b"\x1b\x74\x32"  # WPC1256 Arabic
TXT_ENC_WPC1257 = b"\x1b\x74\x33"  # WPC1257 Baltic Rim
TXT_ENC_WPC1258 = b"\x1b\x74\x34"  # WPC1258 Vietnamese
TXT_ENC_KZ1048 = b"\x1b\x74\x35"  # KZ-1048 Kazakhstan

# Barcod format
BARCODE_TXT_OFF = b"\x1d\x48\x00"  # HRI barcode chars OFF
BARCODE_TXT_ABV = b"\x1d\x48\x01"  # HRI barcode chars above
BARCODE_TXT_BLW = b"\x1d\x48\x02"  # HRI barcode chars below
BARCODE_TXT_BTH = b"\x1d\x48\x03"  # HRI barcode chars both above and below
BARCODE_FONT_A = b"\x1d\x66\x00"  # Font type A for HRI barcode chars
BARCODE_FONT_B = b"\x1d\x66\x01"  # Font type B for HRI barcode chars
BARCODE_HEIGHT = b"\x1d\x68\x64"  # Barcode Height [1-255]
BARCODE_WIDTH = b"\x1d\x77\x03"  # Barcode Width  [2-6]
BARCODE_UPC_A = b"\x1d\x6b\x00"  # Barcode type UPC-A
BARCODE_UPC_E = b"\x1d\x6b\x01"  # Barcode type UPC-E
BARCODE_EAN13 = b"\x1d\x6b\x02"  # Barcode type EAN13
BARCODE_EAN8 = b"\x1d\x6b\x03"  # Barcode type EAN8
BARCODE_CODE39 = b"\x1d\x6b\x04"  # Barcode type CODE39
BARCODE_ITF = b"\x1d\x6b\x05"  # Barcode type ITF
BARCODE_NW7 = b"\x1d\x6b\x06"  # Barcode type NW7
# Image format
S_RASTER_N = b"\x1d\x76\x30\x00"  # Set raster image normal size
S_RASTER_2W = b"\x1d\x76\x30\x01"  # Set raster image double width
S_RASTER_2H = b"\x1d\x76\x30\x02"  # Set raster image double height
S_RASTER_Q = b"\x1d\x76\x30\x03"  # Set raster image quadruple
