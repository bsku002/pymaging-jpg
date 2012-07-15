"""
Based on C++ code by Dr. Tony Lin:
/******************************************************************************
*    Author:            Dr. Tony Lin                                            *
*    Email:            lintong@cis.pku.edu.cn                                    *
*    Release Date:    Dec. 2002                                                *
*                                                                            *
*    Name:            TonyJpegLib, rewritten from IJG codes                    *
*    Source:            IJG v.6a JPEG LIB                                        *
*    Purpose:        Support real jpeg file, with readable code                *
*                                                                            *
*    Acknowlegement:    Thanks for great IJG, and Chris Losinger                *
*                                                                            *
*    Legal Issues:    (almost same as IJG with followings)                    *
*                                                                            *
*    1. We don't promise that this software works.                            *
*    2. You can use this software for whatever you want.                        *
*    You don't have to pay.                                                    *
*    3. You may not pretend that you wrote this software. If you use it        *
*    in a program, you must acknowledge somewhere. That is, please            *
*    metion IJG, and Me, Dr. Tony Lin.                                        *
*                                                                            *
*****************************************************************************/
"""
# The license is based off the license used by libjpeg
from pymaging_jpg.compat import byteord
from functools import reduce


# JPEG marker codes
M_SOF0  = 0xc0
M_SOF1  = 0xc1
M_SOF2  = 0xc2
M_SOF3  = 0xc3

M_SOF5  = 0xc5
M_SOF6  = 0xc6
M_SOF7  = 0xc7

M_JPG   = 0xc8
M_SOF9  = 0xc9
M_SOF10 = 0xca
M_SOF11 = 0xcb

M_SOF13 = 0xcd
M_SOF14 = 0xce
M_SOF15 = 0xcf

M_DHT   = 0xc4

M_DAC   = 0xcc

M_RST0  = 0xd0
M_RST1  = 0xd1
M_RST2  = 0xd2
M_RST3  = 0xd3
M_RST4  = 0xd4
M_RST5  = 0xd5
M_RST6  = 0xd6
M_RST7  = 0xd7

M_SOI   = 0xd8
M_EOI   = 0xd9
M_SOS   = 0xda
M_DQT   = 0xdb
M_DNL   = 0xdc
M_DRI   = 0xdd
M_DHP   = 0xde
M_EXP   = 0xdf

M_APP0  = 0xe0
M_APP1  = 0xe1
M_APP2  = 0xe2
M_APP3  = 0xe3
M_APP4  = 0xe4
M_APP5  = 0xe5
M_APP6  = 0xe6
M_APP7  = 0xe7
M_APP8  = 0xe8
M_APP9  = 0xe9
M_APP10 = 0xea
M_APP11 = 0xeb
M_APP12 = 0xec
M_APP13 = 0xed
M_APP14 = 0xee
M_APP15 = 0xef

M_JPG0  = 0xf0
M_JPG13 = 0xfd
M_COM   = 0xfe

M_TEM   = 0x01

M_ERROR = 0x100

# jpeg_natural_order[i] is the natural-order position of the i'th
# element of zigzag order.

# When reading corrupted data, the Huffman decoders could attempt
# to reference an entry beyond the end of this array (if the decoded
# zero run length reaches past the end of the block).  To prevent
# wild stores without adding an inner-loop test, we put some extra
# "63"s after the real entries.  This will cause the extra coefficient
# to be stored in location 63 of the block, not somewhere random.
# The worst case would be a run-length of 15, which means we need 16
# fake entries.

jpeg_natural_order = [
    0,  1,  8, 16,  9,  2,  3, 10,
    17, 24, 32, 25, 18, 11,  4,  5,
    12, 19, 26, 33, 40, 48, 41, 34,
    27, 20, 13,  6,  7, 14, 21, 28,
    35, 42, 49, 56, 57, 50, 43, 36,
    29, 22, 15, 23, 30, 37, 44, 51,
    58, 59, 52, 45, 38, 31, 39, 46,
    53, 60, 61, 54, 47, 55, 62, 63,
    63, 63, 63, 63, 63, 63, 63, 63, # extra entries for safety
    63, 63, 63, 63, 63, 63, 63, 63
]


class JPEGComponentInfo(object):
    component_id = 0        # identifier for this component (0..255)
    component_index = 0        # its index in SOF or cinfo->comp_info[]
    h_samp_factor = 0        # horizontal sampling factor (1..4)
    v_samp_factor = 0        # vertical sampling factor (1..4)
    quant_tbl_no = 0        # quantization table selector (0..3)


class HuffTable(object):
    def __init__(self):
        self.mincode = [0]*17
        self.maxcode = [0]*18
        self.valptr = [0]*17
        self.bits = [0]*17
        self.huffval = [0]*256
        self.look_nbits = [0]*256
        self.look_sym = [0]*256

    def compute(self):
        """Compute the derived values for a Huffman table."""
        # Figure C.1: make table of Huffman code length for each symbol
        # Note that this is in code-length order.
        p = 0
        huffsize = [0]*257
        huffcode = [0]*257
        for l in range(1,17):
            for _ in range(1, self.bits[l] + 1):
                huffsize[p] = l
                p += 1
        huffsize[p] = 0

        # Figure C.2: generate the codes themselves
        # Note that this is in code-length order.

        code = 0
        si = huffsize[0]
        p = 0
        while huffsize[p]:
            while huffsize[p] == si:
                huffcode[p] = code
                code += 1
                p += 1
            code <<= 1
            si += 1

        # Figure F.15: generate decoding tables for bit-sequential decoding

        p = 0
        for l in range(1, 17):
            if self.bits[l]:
                self.valptr[l] = p               # huffval[] index of 1st symbol of code length l
                self.mincode[l] = huffcode[p]    # minimum code of length l
                p += self.bits[l]
                self.maxcode[l] = huffcode[p-1]  # maximum code of length l
            else:
                self.maxcode[l] = -1             # -1 if no codes of this length
        self.maxcode[17] = 0xFFFFF  # ensures jpeg_huff_decode terminates

        """ Compute lookahead tables to speed up decoding.
         First we set all the table entries to 0, indicating "too long"
         then we iterate through the Huffman codes that are short enough and
         fill in all the entries that correspond to bit sequences starting
         with that code.     """
        self.look_nbits = [0]*256
        HUFF_LOOKAHEAD = 8
        p = 0
        for l in range(1, HUFF_LOOKAHEAD+1):
            for _ in range(1, self.bits[l]+1):
                """ l = current code's length,
                p = its index in huffcode[] & huffval[]. Generate left-justified
                code followed by all possible bit sequences """
                lookbits = huffcode[p] << (HUFF_LOOKAHEAD-l)
                ctr = 1 << (HUFF_LOOKAHEAD-l)
                while ctr > 0:
                    self.look_nbits[lookbits] = l
                    self.look_sym[lookbits] = self.huffval[p]
                    lookbits += 1
                    ctr -= 1
                p += 1


class TonyJpegDecoder(object):
    def __init__(self):
        """set up the decoder"""
        self.Quality = 0
        self.Scale = 0
        self.tblRange = [0]*(5*256+128)
        # To speed up, we save YCbCr=>RGB color map tables
        self.CrToR = {}
        self.CrToG = {}
        self.CbToB = {}
        self.CbToG = {}
        # To speed up, we precompute two DCT quant tables
        self.qtblY = {}
        self.qtblCbCr = {}
        self.htblYDC = HuffTable()
        self.htblYAC = HuffTable()
        self.htblCbCrDC = HuffTable()
        self.htblCbCrAC = HuffTable()
        # per image parameters
        self.Width = 0
        self.Height = 0
        self.McuSize = 0
        self.BlocksInMcu = 0
        self.dcY = 0
        self.dcCb = 0
        self.dcCr = 0
        self.GetBits = 0
        self.GetBuff = 0
        self.DataBytesLeft = 0
        self.Data = ""
        self.DataPos = 0
        self.Precision = 0
        self.Component = 0
        self.restart_interval = 0
        self.restarts_to_go = 0
        self.unread_marker = 0
        self.next_restart_num = 0
        self.comp_info = [JPEGComponentInfo(), JPEGComponentInfo(), JPEGComponentInfo()]

    def read_headers(self, jpegsrc):
        """reads Width, Height, headsize"""
        self.read_markers(jpegsrc)
        if self.Width <= 0 or self.Height <= 0:
            raise ValueError("Error reading the file header")
        self.DataBytesLeft = len(jpegsrc) - self.DataPos
        self.init_decoder()

    def read_byte(self):
        byte = self.Data[self.DataPos]
        self.DataPos += 1
        output = byteord(byte)
        return output

    def read_word(self):
        byte1, byte2 = self.Data[self.DataPos:self.DataPos+2]
        self.DataPos += 2
        output = (byteord(byte1)<<8) + byteord(byte2)
        return output

    def read_one_marker(self):
        """read exact marker, two bytes, no stuffing allowed"""
        if self.read_byte() != 255:
            raise ValueError("error reading one marker")
        return self.read_byte()

    def skip_marker(self):
        """Skip over an unknown or uninteresting variable-length marker"""
        length = self.read_word()
        self.DataPos += length - 2

    def get_dqt(self):
        length = self.read_word() - 2
        while length > 0:
            n = self.read_byte()
            length -= 1
            n &= 0x0F
            if n == 0:
                qtb = self.qtblY
            else:
                qtb = self.qtblCbCr
            for i in range(64):
                qtb[jpeg_natural_order[i]] = self.read_byte()
            length -= 64


    def get_sof (self, is_prog, is_arith):
        """get Width and Height, and component info"""
        length = self.read_word()
        self.Precision = self.read_byte()
        self.Height = self.read_word()
        self.Width = self.read_word()
        self.Component = self.read_byte()
        length -= 8
        for ci in range(self.Component):
            comp = JPEGComponentInfo()
            comp.component_index = ci
            comp.component_id = self.read_byte()
            c = self.read_byte()
            comp.h_samp_factor = (c >> 4) & 15
            comp.v_samp_factor = (c     ) & 15
            comp.quant_tbl_no = self.read_byte()
            self.comp_info[ci] = comp
        if self.comp_info[0].h_samp_factor == 1 and self.comp_info[0].v_samp_factor == 1:
            self.McuSize = 8
            self.BlocksInMcu = 3
        else:
            self.McuSize = 16
            self.BlocksInMcu = 6

    def get_dht(self):
        length = self.read_word() - 2
        while length > 0:
            index = self.read_byte()
            htbl = HuffTable()
            count = 0
            # read in bits[]
            htbl.bits[0] = 0
            for i in range(1, 17):
                htbl.bits[i] = self.read_byte()
                count += htbl.bits[i]
            # read in huffval
            for i in range(count):
                htbl.huffval[i] = self.read_byte()
            length -= count + 17
            if index == 0:
                self.htblYDC = htbl
            elif index == 16:
                self.htblYAC = htbl
            elif index == 1:
                self.htblCbCrDC = htbl
            elif index == 17:
                self.htblCbCrAC = htbl

    def get_sos(self):
        self.read_word()
        # number of components
        n = self.read_byte()
        # Collect the component-spec parameters
        for _ in range(n):
            self.read_byte()
            self.read_byte()
            # find the match comp_id; Current we do nothing
            # (the C code here is commented out)
        # Collect the additional scan parameters Ss, Se, Ah/Al.
        self.read_byte()
        self.read_byte()
        self.read_byte()
        self.next_restart_num = 0

    def get_dri(self):
        self.length = self.read_word()
        self.restart_interval = self.read_word()
        self.restarts_to_go = self.restart_interval

    def read_markers(self, inbuf):
        """raises an error or returns if successfull"""
        self.Data = inbuf
        while True:
            # IJG use first_marker() and next_marker()
            marker = self.read_one_marker()
            # read more info according to the marker
            # the order of cases is in jpg file made by ms paint
            if marker == M_SOI:
                # if not self.get_soi(cinfo):
                #   return -1  # JPEG_SUSPENDED
                pass
            elif marker in (M_APP0, M_APP1, M_APP2, M_APP3, M_APP4, M_APP5, M_APP6, M_APP7, M_APP8, M_APP9, M_APP10, M_APP11, M_APP12, M_APP13, M_APP14, M_APP15):
                self.skip_marker() # JFIF APP0 marker, or Adobe APP14 marker
            elif marker == M_DQT:
                # maybe twice, one for Y, another for Cb/Cr
                self.get_dqt()
            elif marker in (M_SOF0, M_SOF1): # Baseline, Extended sequential (Huffman)
                self.get_sof(False, False)
            elif marker == M_SOF2:
                # Progressive, Huffman
                raise ValueError("Prog + Huff is not supported")
            elif marker == M_SOF9:
                # Extended sequential, arithmetic
                raise ValueError("Sequential + Arith is not supported")
            elif marker == M_SOF10:
                # Progressive, arithmetic
                raise ValueError("Prog + Arith is not supported")
            elif marker == M_DHT:
                # 4 tables: dc/ac * Y/CbCr
                self.get_dht()
            elif marker == M_SOS:
                # Start of Scan
                self.get_sos()
                return
            elif marker == M_COM:
                # the following marker are not needed for jpg made by ms paint
                self.skip_marker()
            elif marker == M_DRI:
                self.get_dri()
            # elif marker in (M_SOF3, M_SOF5, M_SOF6, M_SOF7, M_JPG, M_SOF11, M_SOF13, M_SOF14, M_SOF15):
            # # currently unsupported SOFn types:
            #   raise ValueError("Unsupported marker: %d" % marker)
            # elif marker == M_EOI:
            #   # TODO: handle this properly
            #   self.cinfo.unread_marker = 0
            #   return 1 # JPEG_REACHED_EOI
            # elif marker == M_DAC:
            #   if not self.get_dac(cinfo):
            #     return -1 # JPEG_SUSPENDED
            # elif marker in (M_RST0, M_RST1, M_RST2, M_RST3, M_RST4, M_RST5, M_RST6, M_RST7, M_TEM):
            # # these are all parameterless
            #   pass
            # elif marker == M_DNL:
            # # Ignore DNL ... perhaps the wrong thing
            #   if not self.skip_variable(cinfo):
            #     return -1 # JPEC_SUSPENDED
            else:
                # must be DHP, EXP, JPGn, or RESn
                # For now, we treat the reserved markers as fatal errors since they are
                # likely to be used to signal incompatible JPEG Part 3 extensions.
                # Once the JPEG 3 version-number marker is well defined, this code
                # ought to change!
                raise ValueError("Unknown marker: 0x%x" % marker)

            # Successfully processed marker, so reset state variable
            self.unread_marker = 0

    def read_restart_marker(self):
        # Obtain a marker unless we already did.
        # Note that next_marker will complain if it skips any data.
        if self.unread_marker == 0:
            self.unread_marker = self.read_one_marker()
        if self.unread_marker == M_RST0 + self.next_restart_num:
            # Normal case --- swallow the marker and let entropy decoder continue
            self.unread_marker = 0
        else:
            # Uh-oh, the restart markers have been messed up.
            # Let the data source manager determine how to resync.
            # if not cinfo.src.resync_to_restart(cinfo, cinfo.marker.next_restart_num):
            #   return False
            pass
        self.next_restart_num = (self.next_restart_num + 1) & 7

    def init_decoder(self):
        """
        Prepare for all the tables needed,
        eg. quantization tables, huff tables, color convert tables
        1 <= nQuality <= 100, is used for quantization scaling
        Computing once, and reuse them again and again !!!!!!!
        """
        self.GetBits = 0
        self.GetBuff = 0
        self.dcY = 0
        self.dcCb = 0
        self.dcCr = 0
        # prepare range limiting table to limit idct outputs
        self.set_range_table()
        # convert table, from bgr to ycbcr
        self.init_color_table()
        # prepare two quant tables, one for Y, and another for CbCr
        self.init_quant_table()
        # prepare four huffman tables:
        self.init_huffman_table()

    def set_range_table(self):
        """
        prepare_range_limit_table(): Set self.tblRange[5*256+128 = 1408]
        range table is used for range limiting of idct results
        On most machines, particularly CPUs with pipelines or instruction prefetch,
        a (subscript-check-less) C table lookup
              x = sample_range_limit[x]
        is faster than explicit tests
                if (x < 0)  x = 0
                else if (x > MAXJSAMPLE)  x = MAXJSAMPLE
        """
        # self.tblRange[0, ..., 255], limit[x] = 0 for x < 0
        # self.tblRange[256, ..., 511], limit[x] = x
        # self.tblRange[512, ..., 895]: first half of post-IDCT table
        # self.tblRange[896, ..., 1280]: Second half of post-IDCT table
        # self.tblRange[1280, 1407] = self.tblRange[256, 384]
        self.tblRange = [0]*256 + list(range(256)) + [255]*(512-128) + [0]*384 + list(range(128))

        """YCbCr -> RGB conversion: most common case

        YCbCr is defined per CCIR 601-1, except that Cb and Cr are
        normalized to the range 0..MAXJSAMPLE rather than -0.5 .. 0.5.
        The conversion equations to be implemented are therefore
             R = Y                + 1.40200 * Cr
             G = Y - 0.34414 * Cb - 0.71414 * Cr
             B = Y + 1.77200 * Cb
        where Cb and Cr represent the incoming values less CENTERJSAMPLE.
        (These numbers are derived from TIFF 6.0 section 21, dated 3-June-92.)

        To avoid floating-point arithmetic, we represent the fractional constants
        as integers scaled up by 2^16 (about 4 digits precision); we have to divide
        the products by 2^16, with appropriate rounding, to get the correct answer.
        Notice that Y, being an integral input, does not contribute any fraction
        so it need not participate in the rounding.

        For even more speed, we avoid doing any multiplications in the inner loop
        by precalculating the constants times Cb and Cr for all possible values.
        For 8-bit JSAMPLEs this is very reasonable (only 256 entries per table)
        for 12-bit samples it is still acceptable.  It's not very reasonable for
        16-bit samples, but if you want lossless storage you shouldn't be changing
        colorspace anyway.
        The Cr=>R and Cb=>B values can be rounded to integers in advance; the
        values for the G calculation are left scaled up, since we must add them
        together before rounding.
        """

    def init_color_table(self):
        # i is the actual input pixel value, in the range 0..MAXJSAMPLE
        nScale = 1 << 16 # equal to pow(2,16)
        nHalf = nScale >> 1
        FIX = lambda x: int((x) * nScale + 0.5)
        for i in range(256):
            # The Cb or Cr value we are thinking of is x = i - CENTERJSAMPLE
            # We also add in ONE_HALF so that need not do it in inner loop
            x = i - 128
            # Cr=>R value is nearest int to 1.40200 * x
            self.CrToR[i] = (int) ( FIX(1.40200) * x + nHalf ) >> 16
            # Cb=>B value is nearest int to 1.77200 * x
            self.CbToB[i] = (int) ( FIX(1.77200) * x + nHalf ) >> 16
            # Cr=>G value is scaled-up -0.71414 * x
            self.CrToG[i] = (int) (- FIX(0.71414) * x)
            # Cb=>G value is scaled-up -0.34414 * x
            self.CbToG[i] = (int) (- FIX(0.34414) * x + nHalf)

    def init_quant_table(self):
        """init_quant_table will produce customized quantization table into: self.tblYQuant[0..63] and self.tblCbCrQuant[0..63]"""
        # These are the sample quantization tables given in JPEG spec section K.1.
        # The spec says that the values given produce "good" quality, and
        # when divided by 2, "very good" quality.

        #   scalefactor[0] = 1
        #   scalefactor[k] = cos(k*PI/16) * sqrt(2)    for k=1..7
        # We apply a further scale factor of 8.
        aanscales = [
          # precomputed values scaled up by 14 bits
          16384, 22725, 21407, 19266, 16384, 12873,  8867,  4520,
          22725, 31521, 29692, 26722, 22725, 17855, 12299,  6270,
          21407, 29692, 27969, 25172, 21407, 16819, 11585,  5906,
          19266, 26722, 25172, 22654, 19266, 15137, 10426,  5315,
          16384, 22725, 21407, 19266, 16384, 12873,  8867,  4520,
          12873, 17855, 16819, 15137, 12873, 10114,  6967,  3552,
           8867, 12299, 11585, 10426,  8867,  6967,  4799,  2446,
           4520,  6270,  5906,  5315,  4520,  3552,  2446,  1247]
        def ScaleQuantTable(tblStd, tblAan):
            half = 1 << 11
            # scaling needed for AA&N algorithm
            return [(tblStd[i] * tblAan[i] + half) >> 12 for i in range(64)]

        # Scale the Y and CbCr quant table, respectively
        self.qtblY = ScaleQuantTable(self.qtblY, aanscales)
        self.qtblCbCr = ScaleQuantTable(self.qtblCbCr, aanscales)
        # If no qtb got from jpg file header, then use std quant tbl
        # self.qtblY = ScaleQuantTable(std_luminance_quant_tbl, aanscales)
        # self.qtblCbCr = ScaleQuantTable(std_chrominance_quant_tbl, aanscales)

    def init_huffman_table(self):
        """Prepare four Huffman tables:
           HUFFMAN_TABLE self.htblYDC, self.htblYAC, self.htblCbCrDC, self.htblCbCrAC"""
        #    Using dht got from jpeg file header
        self.htblYDC.compute()
        self.htblYAC.compute()
        self.htblCbCrDC.compute()
        self.htblCbCrAC.compute()


    def decode(self, inbuf):
        """decode(), the main function in this class !!
           inbuf is source data in jpg format
           return is bmp bgr format, bottom_up"""
        self.read_headers(inbuf)
        outbuf = [0] * (self.Width * self.Height * 3)
        #    horizontal and vertical count of tile, macroblocks,
        #    MCU(Minimum Coded Unit),
        #        case 1: maybe is 16*16 pixels, 6 blocks
        #        case 2: may be 8*8 pixels, only 3 blocks
        cxTile = (self.Width  + self.McuSize - 1) / self.McuSize
        cyTile = (self.Height + self.McuSize - 1) / self.McuSize

        #    BMP row width, must be divided by 4
        nRowBytes = (self.Width * 3 + 3) // 4 * 4

        # FIXME: source ptr (don't need to read as we already read the header)
        # self.Data = inbuf
        # self.DataPos = 0
        #    Decompress all the tiles, or macroblocks, or MCUs
        for yTile in range(int(cyTile)):
            # print "decompressing row %d/%d" % (yTile, cyTile)
            for xTile in range(int(cxTile)):
            # Decompress one macroblock started from self.Data
            # This function will push self.Data ahead
            # Result is storing in byTile
                byTile = self.decompress_one_tile()

                #    Get tile starting pixel position
                xPixel = xTile * self.McuSize
                yPixel = yTile * self.McuSize

                #    Get the true number of tile columns and rows
                nTrueRows = self.McuSize
                nTrueCols = self.McuSize
                if yPixel + nTrueRows > self.Height:
                    nTrueRows = self.Height - yPixel
                if xPixel + nTrueCols > self.Width:
                    nTrueCols = self.Width - xPixel

                #    Invert output, to bmp format; row 0=>row (self.Height-1)
                outbufpos = (self.Height - 1 - yPixel) * nRowBytes + xPixel * 3
                for y in range(nTrueRows):
                    offset = y * self.McuSize * 3
                    tilerow = byTile[offset:offset + nTrueCols*3]
                    outbuf[outbufpos:outbufpos + nTrueCols*3] = tilerow
                    outbufpos -= nRowBytes
        return outbuf

# //////////////////////////////////////////////////////////////////////////////
#    function Purpose:    decompress one 16*16 pixels
#    source is self.Data
#    This function will push self.Data ahead for next tile

    def decompress_one_tile(self):
        """decompress one 16*16 pixel tile. returns output in BGR format, 16*16*3"""
        # Process restart marker if needed; may have to suspend
        if self.restart_interval:
            if self.restarts_to_go == 0:
                self.GetBits = 0
                self.read_restart_marker()
                self.dcY, self.dcCb, self.dcCr = 0, 0, 0
                self.restarts_to_go = self.restart_interval

        pYCbCr = []
        #    Do Y/Cb/Cr components,
        #    if self.BlocksInMcu==6,  Y: 4 blocks; Cb: 1 block; Cr: 1 block
        #    if self.BlocksInMcu==3,  Y: 1 block; Cb: 1 block; Cr: 1 block
        for i in range(self.BlocksInMcu):
            coeff = self.huffman_decode(i)    # source is self.Data
            # print "huff[%d]: %s" % (i, " ".join(["%02x" % coeff[i] for i in range(64)]))
            pYCbCr += self.inverse_dct(coeff, i)    # De-scale and inverse dct
        #    Color conversion and up-sampling
        tileoutput = self.YCbCr_to_BGREx(pYCbCr)
        # print "pbgr[%d]: %s" % (self.DataPos, " ".join(["%02x" % i for i in tileoutput]))

        # Account for restart interval (no-op if not using restarts)
        self.restarts_to_go -= 1

        return tileoutput


# //////////////////////////////////////////////////////////////////////////////
#    if self.BlocksInMcu==3, no need to up-sampling

    def YCbCr_to_BGREx(self, pYCbCr):
        """Color conversion and up-sampling
        in, Y: 256 or 64 bytes; Cb: 64 bytes; Cr: 64 bytes
        out, BGR format, 16*16*3 = 768 bytes; or 8*8*3=192 bytes"""
        # py is meant to function like a set of pointers into pYCbCr
        pyoffset = [i*64 for i in range(self.BlocksInMcu-2)]
        pcboffset = (self.BlocksInMcu-2) * 64
        pcroffset = pcboffset + 64
        # this is to handle negative offsets...
        range_limit = self.tblRange[256:] + self.tblRange[:256]
        pByte = []
        for j in range(self.McuSize): # vertical axis
            for i in range(self.McuSize): # horizontal axis:
            # block number is ((j/2) * 8 + i/2)={0, 1, 2, 3}
                blocknum = ((j//2) * 8 + i//2)
                # if self.McuSize==8, will use py[0]
                pyindex = (j>>3) * 2 + (i>>3)
                y = pYCbCr[pyoffset[pyindex]]
                pyoffset[pyindex] += 1
                iblocknum = int(blocknum)
                cb = pYCbCr[pcboffset + iblocknum]
                cr = pYCbCr[pcroffset + iblocknum]
                # print "blue", y, self.CbToB[cb], len(pYCbCr), len(range_limit)
                blue = range_limit[ y + self.CbToB[cb] ]
                green = range_limit[ y + ((self.CbToG[cb] + self.CrToG[cr]) >> 16) ]
                red = range_limit[ y + self.CrToR[cr] ]
                # print "ycbcr %d %d %d %d %d / %d %d" % (j, i, y, cb, cr, pyindex, blocknum)
                # print "exbgr %d %d %d / %d %d %d / %d %d %d %d" % (j, i, y, blue, green, red, self.CbToB[cb], self.CbToG[cb], self.CrToG[cr], self.CrToR[cr])
                # print "exred %d %d %d / %d %d %d / %d %d %d / %d" % (j, i, y, pyoffset[(j>>3) * 2 + (i>>3)], pYCbCr[pcroffset + j/2 * 8 + i/2], cr, self.CrToR[cr], y + self.CrToR[cr], range_limit[ y + self.CrToR[cr] ], red)
                pByte += [blue, green, red]
        return pByte

    def inverse_dct(self, coeff, nBlock):
        """AA&N DCT algorithm implemention
            coeff             # in, dct coefficients, length = 64
            data             # out, 64 bytes
            nBlock           # block index: 0~3:Y; 4:Cb; 5:Cr
        """

        FIX_1_082392200 = 277        # FIX(1.082392200)
        FIX_1_414213562 = 362        # FIX(1.414213562)
        FIX_1_847759065 = 473        # FIX(1.847759065)
        FIX_2_613125930 = 669        # FIX(2.613125930)

        MULTIPLY = lambda var, cons: int(var*cons)>>8

        workspace = [0]*64        # buffers data between passes

        inptr = 0
        wsptr = 0 # pointer into workspace
        outbuf = [0]*64
        outptr = 0
        range_limit = self.tblRange[256+128:]
        dcval, DCTSIZE = 0, 8

        if nBlock < 4:
            quant = self.qtblY
        else:
            quant = self.qtblCbCr
        quantptr = 0

        # Pass 1: process columns from input (inptr), store into work array(wsptr)
        for ctr in range(8, 0, -1):
            # Due to quantization, we will usually find that many of the input
            # coefficients are zero, especially the AC terms.  We can exploit this
            # by short-circuiting the IDCT calculation for any column in which all
            # the AC terms are zero.  In that case each output is equal to the
            # DC coefficient (with scale factor as needed).
            # With typical images and quantization tables, half or more of the
            # column DCT calculations can be simplified this way.
            if reduce(int.__or__, map(int, [coeff[inptr+DCTSIZE*n] for n in range(1,8)])) == 0:
                """ AC terms all zero """
                dcval = coeff[inptr + DCTSIZE*0] * quant[quantptr+DCTSIZE*0]

                workspace[wsptr+DCTSIZE*0] = dcval
                workspace[wsptr+DCTSIZE*1] = dcval
                workspace[wsptr+DCTSIZE*2] = dcval
                workspace[wsptr+DCTSIZE*3] = dcval
                workspace[wsptr+DCTSIZE*4] = dcval
                workspace[wsptr+DCTSIZE*5] = dcval
                workspace[wsptr+DCTSIZE*6] = dcval
                workspace[wsptr+DCTSIZE*7] = dcval

                # advance pointers to next column
                inptr += 1
                quantptr += 1
                wsptr += 1
                continue

            # Even part

            tmp0 = coeff[inptr+DCTSIZE*0] * quant[quantptr+DCTSIZE*0]
            tmp1 = coeff[inptr+DCTSIZE*2] * quant[quantptr+DCTSIZE*2]
            tmp2 = coeff[inptr+DCTSIZE*4] * quant[quantptr+DCTSIZE*4]
            tmp3 = coeff[inptr+DCTSIZE*6] * quant[quantptr+DCTSIZE*6]
            # phase 3
            tmp10 = tmp0 + tmp2
            tmp11 = tmp0 - tmp2
            # phases 5-3
            tmp13 = tmp1 + tmp3
            # 2*c4
            tmp12 = MULTIPLY(tmp1 - tmp3, FIX_1_414213562) - tmp13
            # phase 2
            tmp0 = tmp10 + tmp13
            tmp3 = tmp10 - tmp13
            tmp1 = tmp11 + tmp12
            tmp2 = tmp11 - tmp12

            # Odd part

            tmp4 = coeff[inptr+DCTSIZE*1] * quant[quantptr+DCTSIZE*1]
            tmp5 = coeff[inptr+DCTSIZE*3] * quant[quantptr+DCTSIZE*3]
            tmp6 = coeff[inptr+DCTSIZE*5] * quant[quantptr+DCTSIZE*5]
            tmp7 = coeff[inptr+DCTSIZE*7] * quant[quantptr+DCTSIZE*7]
            # phase 6
            z13 = tmp6 + tmp5
            z10 = tmp6 - tmp5
            z11 = tmp4 + tmp7
            z12 = tmp4 - tmp7
            # phase 5
            tmp7  = z11 + z13
            tmp11 = MULTIPLY(z11 - z13, FIX_1_414213562)    # 2*c4

            z5      = MULTIPLY(z10 + z12, FIX_1_847759065)    # 2*c2
            tmp10 = MULTIPLY(z12, FIX_1_082392200) - z5    # 2*(c2-c6)
            tmp12 = MULTIPLY(z10, - FIX_2_613125930) + z5    # -2*(c2+c6)
            # phase 2
            tmp6 = tmp12 - tmp7
            tmp5 = tmp11 - tmp6
            tmp4 = tmp10 + tmp5

            workspace[wsptr+DCTSIZE*0] = int(tmp0 + tmp7)
            workspace[wsptr+DCTSIZE*7] = int(tmp0 - tmp7)
            workspace[wsptr+DCTSIZE*1] = int(tmp1 + tmp6)
            workspace[wsptr+DCTSIZE*6] = int(tmp1 - tmp6)
            workspace[wsptr+DCTSIZE*2] = int(tmp2 + tmp5)
            workspace[wsptr+DCTSIZE*5] = int(tmp2 - tmp5)
            workspace[wsptr+DCTSIZE*4] = int(tmp3 + tmp4)
            workspace[wsptr+DCTSIZE*3] = int(tmp3 - tmp4)
            # advance pointers to next column
            inptr += 1
            quantptr += 1
            wsptr += 1

        # Pass 2: process rows from work array, store into output array.
        # Note that we must descale the results by a factor of 8 == 2**3,
        # and also undo the PASS1_BITS scaling.

        RANGE_MASK = 1023 # 2 bits wider than legal samples
        PASS1_BITS = 2
        IDESCALE = lambda x,n:  x >> n

        wsptr = 0
        for ctr in range(DCTSIZE):
            outptr = ctr * 8

            # Rows of zeroes can be exploited in the same way as we did with columns.
            # However, the column calculation has created many nonzero AC terms, so
            # the simplification applies less often (typically 5% to 10% of the time).
            # On machines with very fast multiplication, it's possible that the
            # test takes more time than it's worth.  In that case this section
            # may be commented out.
            if reduce(int.__or__, workspace[wsptr+1:wsptr+8]) == 0:
                # AC terms all zero
                dcval = range_limit[ (workspace[wsptr] >> 5) & RANGE_MASK]
                outbuf[outptr+0] = dcval
                outbuf[outptr+1] = dcval
                outbuf[outptr+2] = dcval
                outbuf[outptr+3] = dcval
                outbuf[outptr+4] = dcval
                outbuf[outptr+5] = dcval
                outbuf[outptr+6] = dcval
                outbuf[outptr+7] = dcval
                wsptr += DCTSIZE # advance pointer to next row
                continue

            # Even part

            tmp10 = ( workspace[wsptr+0] +  workspace[wsptr+4])
            tmp11 = ( workspace[wsptr+0] -  workspace[wsptr+4])

            tmp13 = ( workspace[wsptr+2] +  workspace[wsptr+6])
            tmp12 = MULTIPLY( workspace[wsptr+2] -  workspace[wsptr+6], FIX_1_414213562) - tmp13

            tmp0 = tmp10 + tmp13
            tmp3 = tmp10 - tmp13
            tmp1 = tmp11 + tmp12
            tmp2 = tmp11 - tmp12

            # Odd part

            z13 =  workspace[wsptr+5] +  workspace[wsptr+3]
            z10 =  workspace[wsptr+5] -  workspace[wsptr+3]
            z11 =  workspace[wsptr+1] +  workspace[wsptr+7]
            z12 =  workspace[wsptr+1] -  workspace[wsptr+7]
            # phase 5
            tmp7 = z11 + z13
            tmp11 = MULTIPLY(z11 - z13, FIX_1_414213562)    # 2*c4

            z5    = MULTIPLY(z10 + z12, FIX_1_847759065)    # 2*c2
            tmp10 = MULTIPLY(z12, FIX_1_082392200) - z5    # 2*(c2-c6)
            tmp12 = MULTIPLY(z10, - FIX_2_613125930) + z5    # -2*(c2+c6)
            # phase 2
            tmp6 = tmp12 - tmp7
            tmp5 = tmp11 - tmp6
            tmp4 = tmp10 + tmp5

            # Final output stage: scale down by a factor of 8 and range-limit

            outbuf[outptr+0] = range_limit[IDESCALE(tmp0 + tmp7, PASS1_BITS+3) & RANGE_MASK]
            outbuf[outptr+7] = range_limit[IDESCALE(tmp0 - tmp7, PASS1_BITS+3) & RANGE_MASK]
            outbuf[outptr+1] = range_limit[IDESCALE(tmp1 + tmp6, PASS1_BITS+3) & RANGE_MASK]
            outbuf[outptr+6] = range_limit[IDESCALE(tmp1 - tmp6, PASS1_BITS+3) & RANGE_MASK]
            outbuf[outptr+2] = range_limit[IDESCALE(tmp2 + tmp5, PASS1_BITS+3) & RANGE_MASK]
            outbuf[outptr+5] = range_limit[IDESCALE(tmp2 - tmp5, PASS1_BITS+3) & RANGE_MASK]
            outbuf[outptr+4] = range_limit[IDESCALE(tmp3 + tmp4, PASS1_BITS+3) & RANGE_MASK]
            outbuf[outptr+3] = range_limit[IDESCALE(tmp3 - tmp4, PASS1_BITS+3) & RANGE_MASK]

            wsptr += DCTSIZE   # advance pointer to next row

        return outbuf

    def huffman_decode(self, iBlock):
        """source is self.Data
            out DCT coefficients
            iBlock  0,1,2,3:Y; 4:Cb; 5:Cr; or 0:Y;1:Cb;2:Cr"""
        if iBlock < self.BlocksInMcu - 2:
            dctbl = self.htblYDC
            actbl = self.htblYAC
            LastDC = "dcY"
        else:
            dctbl = self.htblCbCrDC
            actbl = self.htblCbCrAC
            if iBlock == self.BlocksInMcu - 2:
                LastDC = "dcCb"
            else:
                LastDC = "dcCr"

        coeff = [0]*64

        # Section F.2.2.1: decode the DC coefficient difference
        s = self.get_category(dctbl)             # get dc category number, s

        if s:
            r = self.do_get_bits(s)                 # get offset in this dc category
            s = self.value_from_category(s, r)    # get dc difference value

        # Convert DC difference to actual value, update last_dc_val
        s += getattr(self, LastDC)
        setattr(self, LastDC, s)

        # Output the DC coefficient (assumes jpeg_natural_order[0] = 0)
        coeff[0] = s

        # Section F.2.2.2: decode the AC coefficients
        # Since zeroes are skipped, output area must be cleared beforehand
        k = 1
        while k < 64:
            s = self.get_category( actbl )    # s: (run, category)
            r = s >> 4                       #    r: run length for ac zero, 0 <= r < 16
            s &= 15                          #    s: category for this non-zero ac

            if s:
                k += r                       #    k: position for next non-zero ac
                r = self.do_get_bits(s)               #    r: offset in this ac category
                s = self.value_from_category(s, r)  #    s: ac value

                coeff[ jpeg_natural_order[ k ] ] = s
            else: # s = 0, means ac value is 0 ? Only if r = 15.
                if r != 15:    # means all the left ac are zero
                    break
                k += 15
            k += 1

        return coeff

    def get_category(self, htbl):
        """get category number for dc, or (0 run length, ac category) for ac"""
        #    The max length for Huffman codes is 15 bits; so we use 32 bits buffer
        #    self.GetBuff, with the validated length is self.GetBits.
        #    Usually, more than 95% of the Huffman codes will be 8 or fewer bits long
        #    To speed up, we should pay more attention on the codes whose length <= 8

        #    If left bits < 8, we should get more data
        if self.GetBits < 8:
            self.fill_bit_buffer()

        #    Call special process if data finished; min bits is 1
        if self.GetBits < 8:
            return self.special_decode(htbl, 1)

        #    Peek the first valid byte
        look = ((self.GetBuff>>(self.GetBits - 8))& 0xFF)
        nb = htbl.look_nbits[look]

        if nb:
            self.GetBits -= nb
            return htbl.look_sym[look]
        else:
            # Decode long codes with length >= 9
            return self.special_decode(htbl, 9)

    def fill_bit_buffer(self):
        while self.GetBits < 25:    # #define MIN_GET_BITS  (32-7)
            if self.DataBytesLeft > 0: # Are there some data?
                # Attempt to read a byte
                if self.unread_marker != 0:
                    # can't advance past a marker

                    # There should be enough bits still left in the data segment
                    # if so, just break out of the outer while loop.
                    # if (self.GetBits >= nbits)
                    if (self.GetBits >= 0):
                        break

                uc = byteord(self.Data[self.DataPos])
                self.DataPos += 1
                self.DataBytesLeft -= 1

                # If it's 0xFF, check and discard stuffed zero byte
                if uc == 0xFF:
                    while uc == 0xFF:
                        uc = byteord(self.Data[self.DataPos])
                        self.DataPos += 1
                        self.DataBytesLeft -= 1

                    if uc == 0:
                        # Found FF/00, which represents an FF data byte
                        uc = 0xFF
                    else:
                        # Oops, it's actually a marker indicating end of compressed data.
                        # Better put it back for use later

                        self.unread_marker = uc

                        # There should be enough bits still left in the data segment
                        # if so, just break out of the outer while loop.
                        # if (self.GetBits >= nbits)
                        if (self.GetBits >= 0):
                            break

                self.GetBuff = int(self.GetBuff << 8) | uc
                self.GetBits += 8
            else:
                break

    def do_get_bits(self, nbits):
        if self.GetBits < nbits:
            # we should read nbits bits to get next data
            self.fill_bit_buffer()
        self.GetBits -= nbits
        return (self.GetBuff >> self.GetBits) & ((1<<nbits)-1)


    def special_decode(self, htbl, nMinBits):
        """Special Huffman decode:
        (1) For codes with length > 8
        (2) For codes with length < 8 while data is finished"""
        l = nMinBits

        # HUFF_DECODE has determined that the code is at least min_bits
        # bits long, so fetch that many bits in one swoop.

        code = self.do_get_bits(l)

        # Collect the rest of the Huffman code one bit at a time.
        # This is per Figure F.16 in the JPEG spec.
        while code > htbl.maxcode[l]:
            code <<= 1
            code |= self.do_get_bits(1)
            l += 1

        # With garbage input we may reach the sentinel value l = 17.
        if l > 16:
            return 0            # fake a zero as the safest result

        return htbl.huffval[ htbl.valptr[l] + (code - htbl.mincode[l]) ]

    def value_from_category(self, nCate, nOffset):
        """To find dc or ac value according to category and category offset"""
        # Method 1:
        # On some machines, a shift and add will be faster than a table lookup.
        # define HUFF_EXTEND(x,s) \
        # ((x)< (1<<((s)-1)) ? (x) + (((-1)<<(s)) + 1) : (x))
        # Method 2: Table lookup

        # If (nOffset < half[nCate]), then value is below zero
        # Otherwise, value is above zero, and just the nOffset
        # entry n is 2**(n-1) """
        half =  \
          [ 0, 0x0001, 0x0002, 0x0004, 0x0008, 0x0010, 0x0020, 0x0040, 0x0080,
            0x0100, 0x0200, 0x0400, 0x0800, 0x1000, 0x2000, 0x4000 ]

        # start[i] is the starting value in this category; surely it is below zero
        # entry n is (-1 << n) + 1
        start = \
          [ 0, ((-1)<<1) + 1, ((-1)<<2) + 1, ((-1)<<3) + 1, ((-1)<<4) + 1,
            ((-1)<<5) + 1, ((-1)<<6) + 1, ((-1)<<7) + 1, ((-1)<<8) + 1,
            ((-1)<<9) + 1, ((-1)<<10) + 1, ((-1)<<11) + 1, ((-1)<<12) + 1,
            ((-1)<<13) + 1, ((-1)<<14) + 1, ((-1)<<15) + 1 ]

        if nOffset < half[nCate]:
            return nOffset + start[nCate]
        else:
            return nOffset
