#!/usr/bin/env python
"""Module for communication with and translation of data with a tektronix AWG5000 series."""


import socket
import time
import sys
import numpy as np

class TekAwg(socket.socket):
    """Class which allows communication with a tektronix AWG5000 series (7000 series should work
     as well, but should be tested). This extends the socket class, and uses ethernet TCP/IP
     packets.

    Example:

        AWG_IP = 127.0.0.1
        AWG_PORT = 4001

        awg = tekawg5000.tekawg5000(AWG_IP,AWG_PORT)
        awg.print_waveform_list()
        awg.close()

    """


    def __init__(self, ip, port):
        """Initialize connection and set timout to 500ms

            Raises: socket.error"""
        socket.socket.__init__(self)
        self.connect((ip, port))
        self.settimeout(1)

    def write(self, message, expect_response=False, expected_length=1):
        """Sends text commands to the AWG5000 Series, no newline or return character required

            Args:
                message: str command to be sent to the AWG, multiple commands can be combined
                    with ";" as a separator

                expect_response: BOOL, whether a response is expected from the AWG, if true
                    then it will wait until a message is receieved from the AWG

                expected_length: INT, if a response is expected, this is the number of expected
                    responses to be recieved (usually one from each command sent)

            Returns: Str, response from AWG when expected_response=True, else it returns None

            Raises:
                IOError if a response was expected but not recieved
            """
        return self.__write_helper(message, expect_response, expected_length)

    def __write_helper(self, message, expect_response, expected_length, depth=3, cur_depth=0):
        """This is the helper for the write command, this allows for multiple attempts to recieve
        a response when a response is expected.
        """

        if depth == cur_depth:
            raise IOError("Failed to recieve response. Check to be sure spelling of command is "
                          "correct and there is no newline character at the end of the string.")

        #Send the message
        self.send(message+"\n")

        #if we are expecting a response, wait until we get the full response back, if not, try again
        if expect_response:
            try:
                response = self.recv(10) #Get some response?
                while (len(response.split(";")) < expected_length
                       or len(response) < 1
                       or response[-1] != "\n"):
                    #keep going until we are satisfied
                    response = response+self.recv(100)

                return response.strip() #strip off the "\r\n and return"

            except socket.timeout: #If we time out, try again, print a warning so we know
                cur_depth += 1
                print ("Timeout. Trying to send {} again "
                       "(Attempt {} of {})".format(repr(message.strip()[:100]), cur_depth, depth))
                #try again
                return self.__write_helper(message, expect_response, expected_length, depth, cur_depth)

        #if no response expected, return None
        return None

    def get_error_queue(self):
        err_queue = []
        err_num = int(self.write("*ESR?", True)[0])
        while err_num != 0:
            err_queue.append(self.write("SYSTEM:ERR?",True))
            err_num = int(self.write("*ESR?", True)[0])
        return err_queue

#############  PRINTING SETTINGS   #########################

    def print_waveform_list(self):
        """Prints a formatted list of all the current waveforms in active memory of the AWG.

            Returns: 0  if printed correctly
                     -1 if there was a connection issue

        """
        con_error = False

        #get list of waveforms, and count how many we have
        try:
            waveform_list = self.get_waveform_list()
            num_saved_waveforms = len(waveform_list)
        except IOError:
            return -1

        try:
            waveform_lengths = self.get_waveform_lengths(waveform_list)
        except IOError:
            waveform_lengths = ["" for _ in range(num_saved_waveforms)]
            con_error = True

        try:
            waveform_types = self.get_waveform_type(waveform_list)
        except IOError:
            waveform_types = ["" for _ in range(num_saved_waveforms)]
            con_error = True

        try:
            waveform_date = self.get_waveform_timestamp(waveform_list)
        except IOError:
            waveform_date = ["" for _ in range(0, num_saved_waveforms)]
            con_error = True

        print "\nList of waveforms in memory:"
        print "\nIndex \t Name\t\t\t\t Data Points \tType\t\tDate"
        for i in range(num_saved_waveforms):
            print ('{0:<9}{1: <32}{2: <15}{3:<16}{4:<5}'.format(i+1,
                                                                waveform_list[i],
                                                                waveform_lengths[i],
                                                                waveform_types[i],
                                                                waveform_date[i]))

        if con_error:
            print "\nConnection Error, partial list printed only"
            return -1
        else:
            return 0

    def print_config(self):
        """Print the current configuration of the AWG"""
        print "\n\nCurrent Settings\n"
        print "Hardware ID:     ", self.get_serial()
        print "Run Mode:        ", self.get_run_mode()
        print "Run State:       ", self.get_run_state()
        print "Frequency:       ", self.get_freq()

        cur_waves = self.get_cur_waveform()
        cur_amp = self.get_amplitude()
        cur_offset = self.get_offset()
        chan_state = self.get_chan_state()
        print "\nChannel Settings"
        print ('%-15s%-15s%-15s%-15s%-15s' %
               ("Setting", "Channel 1", "Channel 2", "Channel 3", "Channel 4"))
        print ('%-15s%-15s%-15s%-15s%-15s' %
               ("Waveforms:", cur_waves[0], cur_waves[1], cur_waves[2], cur_waves[3]))
        print ('%-15s%-15s%-15s%-15s%-15s' %
               ("Amplitude (V):", cur_amp[0], cur_amp[1], cur_amp[2], cur_amp[3]))
        print ('%-15s%-15s%-15s%-15s%-15s' %
               ("Offset (V):", cur_offset[0], cur_offset[1], cur_offset[2], cur_offset[3]))
        print ('%-15s%-15s%-15s%-15s%-15s' %
               ("Channel State:", chan_state[0], chan_state[1], chan_state[2], chan_state[3]))


        seq_list = self.get_seq_list()
        print "\nCurrent Sequence:"
        print ('%-15s%-15s%-15s%-15s%-15s%-15s%-15s' %
               ("Index", "Channel 1", "Channel 2", "Channel 3",
                "Channel 4", "Loop Count", "Jump Target"))
        for i in range(len(seq_list)):
            loop_count = self.get_seq_element_loop_cnt(i+1)
            jump_trg = self.get_seq_element_jmp_ind(i+1)
            print ('%-15i%-15s%-15s%-15s%-15s%-15s%-15s' %
                   (i+1, seq_list[i][0], seq_list[i][1], seq_list[i][2],
                    seq_list[i][3], loop_count, jump_trg))

        print ""


################  WAVEFORMS    #############################

    def get_waveform_list(self):
        """Returns a list of all the currently saved waveforms on the AWG"""

        num_saved_waveforms = int(self.write("WLIST:SIZE?", True))

        waveform_list_cmd = 'WLIST:'
        waveform_list_cmd += ";".join(["NAME? "+str(i) for i in range(0, num_saved_waveforms)])

        waveform_list = self.write(waveform_list_cmd, True, num_saved_waveforms).split(";")

        return waveform_list

    def get_waveform_lengths(self, waveform_list):
        """Returns a list of lengths of all saved waveforms on the AWG"""
        if not isinstance(waveform_list, list):
            waveform_list = list(waveform_list)

        num_saved_waveforms = len(waveform_list)

        if num_saved_waveforms > 1:
            waveform_length_cmd = 'WLIST:WAVeform:'+";".join(["LENGTH? "+ i for i in waveform_list])
            waveform_lengths = self.write(waveform_length_cmd, True, num_saved_waveforms).split(";")
        else:
            waveform_length_cmd = 'WLIST:WAVeform:LENGTH? '+str(waveform_list)
            waveform_lengths = self.write(waveform_length_cmd, True).split(";")

        if len(waveform_lengths) == num_saved_waveforms:
            return waveform_lengths
        else:
            raise IOError("Failed to retrieve lengths of all waveforms.")

    def get_waveform_type(self, waveform_list):
        """returns the type of waveform which is stored on the AWG, IE: the AWG saves waveforms
        as either Integer ("INT") or Floating Point ("REAL") representations.

            Args:
                waveform_list: A single waveform name, or list of names

            Returns: list of strings containing either "INT" or "REAL" for int or float

            Raises:
                IOError if fewer types were returned then asked for"""

        if not isinstance(waveform_list, list):
            waveform_list = list(waveform_list)

        num_saved_waveforms = len(waveform_list)

        if num_saved_waveforms > 1:
            waveform_type_cmd = 'WLIST:WAVeform:'+";".join(["TYPE? "+ str(i) for i in waveform_list])
            waveform_type = self.write(waveform_type_cmd, True, num_saved_waveforms).split(";")
        else:
            waveform_type_cmd = 'WLIST:WAVeform:TYPE? '+str(waveform_list)
            waveform_type = self.write(waveform_type_cmd, True).split(";")

        if len(waveform_type) == num_saved_waveforms:
            return waveform_type
        else:
            raise IOError("Failed to retrieve lengths of all waveforms.")

    def get_waveform_timestamp(self, waveform_list):
        """Returns the creation/edit timestamp of waveforms which are stored on the AWG,

            Args:
                waveform_list: A single waveform name, or list of names

            Returns: list of strings containing date of creation or last edit

            Raises:
                IOError if fewer types were returned then asked for"""

        if not isinstance(waveform_list, list):
            waveform_list = list(waveform_list)

        num_saved_waveforms = len(waveform_list)

        if num_saved_waveforms > 1:
            waveform_date_cmd = 'WLIST:WAVeform:'+";".join(["TSTAMP? "+ str(i) for i in waveform_list])
            waveform_date = self.write(waveform_date_cmd, True, num_saved_waveforms).split(";")
        else:
            waveform_date_cmd = 'WLIST:WAVeform:TSTAMP? '+str(waveform_list)
            waveform_date = self.write(waveform_date_cmd, True).split(";")

        if len(waveform_date) == num_saved_waveforms:
            return waveform_date
        else:
            raise IOError("Failed to retrieve lengths of all waveforms.")


    def get_waveform_data(self, filename):
        """"""
        raw_waveform_str = self.__get_waveform_data(filename)
        str_type = self.write('WLISt:WAVeform:TYPE? "'+filename+'"', True)
        return byte_str_to_vals(raw_waveform_str, str_type)


    def __get_waveform_data(self, filename):
        """Get the raw waveform data from the AWG, this will be in the packed format containing
        both the channel waveforms as well as the markers, this needs to be correctly formatted.
            Args:
                filename: name of the file to get from the AWG

            Returns: a string of binary containing the data from the AWG, header has been removed

            Raises:
                IOError if there was a timeout, most likely due to connection or incorrect name
        """
        self.send(str('WLISt:WAVeform:DATA? "'+filename+'"\r\n'))
        time.sleep(.05)

        raw_waveform = ""
        waveform_length = 5
        timeouts = 0
        while len(raw_waveform) < 2 or len(raw_waveform) <= waveform_length:
            if timeouts >= 5:
                raise IOError("Timeout. Failed to get waveform")
            try:
                raw_waveform = "".join([raw_waveform, self.recv(10000)])
            except socket.error as e:
                print e
                time.sleep(1)
                timeouts += 1
            if len(raw_waveform) > 5:
                num_digits = int(raw_waveform[1])
                waveform_length = int(raw_waveform[2:2+num_digits])

        raw_waveform = raw_waveform.strip()[num_digits+2:]

        #waveform = list(struct.unpack("<"+"fx"*(waveform_length/5),raw_waveform))

        return raw_waveform



    def new_waveform(self, filename, packed_data, packet_size=20000):
        """Creates a new waveform on the AWG and saves the data. It has error checking
            in the transmission, after every packet it asks the AWG if it had any issues
            writing the data to memory. If the AWG reports an error it resends that packet.
            This communication guarantees correct waveform on the AWG, but the requesting
            of updates from the AWG adds time to the transmission. There is a tradeoff
            between packet_size and speed of transfer, too large of packets and errors increase,
            too small and it takes longer because of waiting for the AWG to respond that it
            recieved the data correctly.

            Args:
                filename: the name of the new waveform

                packed_data: numpy ndarray or list of the already 'packed' data (both
                            the waveform and markers in an int16 format)

                packet_size: Size of the TCP/IP packet which are sent to the AWG.
                            This has a large effect on speed of transfer and stability.

            Returns:
                None

            Raises:
                IOError: if there was a connection error"""
        packed_data = ints_to_byte_str(packed_data)
        self.__new_waveform_int(filename, packed_data, packet_size)
        return None


    def __new_waveform_int(self, filename, packed_data, packet_size):
        """This is the helper function which actually sends the waveform to the AWG, see above."""
        errs = self.get_error_queue()
        if errs != []:
            print errs,
        data_length = len(packed_data)

        self.settimeout(1)
        if '"'+filename+'"' in self.get_waveform_list():
            self.del_waveform(filename)

        self.write('WLISt:WAVeform:NEW "'+filename+'",'+str(data_length/2)+",INT")

        if data_length >= packet_size*2:
            for i in range(0, data_length/(packet_size*2)):
                prefix = create_prefix(packed_data[i*packet_size*2:(i+1)*packet_size*2])
                packet = packed_data[i*packet_size*2:(i+1)*packet_size*2]
                success = False
                while not success:
                    success = self.write('WLIST:WAVEFORM:DATA "'+filename+'",'
                                         +str(i*packet_size)+','
                                         +str(packet_size)+','
                                         +prefix
                                         +packet
                                         +";*ESR?\r\n", True) == "0"

        remaining_data_size = data_length-data_length/(packet_size*2)*packet_size*2

        if remaining_data_size > 0:
            self.write('WLIST:WAVeform:DATA "'+filename+'",'
                       +str((data_length-remaining_data_size)/2)+','
                       +str(remaining_data_size/2)+","
                       +create_prefix(packed_data[data_length-remaining_data_size:])
                       +packed_data[data_length-remaining_data_size:]
                       +"\r\n")

        errs = self.get_error_queue()
        if errs != []:
            print errs,
        self.settimeout(.5)

    def del_waveform(self, filename):
        """Delete Specified Waveform"""
        self.write('WLISt:WAVeform:DELete "'+filename+'"')



#######################   AWG SETTINGS  ############################

    def get_serial(self):
        """Returns the hardware serial number and ID as a string"""
        return self.write("*IDN?", True)

    def get_freq(self):
        """Returns the current sample rate of the AWG"""
        return float(self.write("FREQ?", True))

    def set_freq(self, freq):
        """Sets the current sample rate of the AWG"""
        self.write("FREQ "+str(freq))

    def get_run_mode(self):
        """Gets the current running mode of the AWG: SEQ, CONT, TRIG, GAT"""
        return self.write("AWGCONTROL:RMODE?", True)

    def set_run_mode(self, mode):
        """Sets the run mode of the AWG, allowed modes are:
            continuous, triggered, gated, sequence"""
        if mode.lower() in ["continuous", "cont",
                            "trigered", "trig",
                            "gated", "gat",
                            "sequence", "seq"]:
            self.write("AWGCONTROL:RMODE "+mode)

    def get_run_state(self):
        """Gets the current state of the AWG, possible states are:
        stopped, waiting for trigger, or running"""
        state = self.write("AWGControl:RSTate?", True)
        if state == "0":
            return "Stopped"
        elif state == "1":
            return "Waiting for Trigger"
        elif state == "2":
            return "Running"
        raise IOError("Not valid run state")

    def run(self):
        """Start running the AWG"""
        self.write("AWGControl:RUN")

    def stop(self):
        """Stop the AWG"""
        self.write("AWGCONTROL:STOP")

    def get_amplitude(self, channel=None):
        if channel is None: channel = [1, 2, 3, 4]
        if not isinstance(channel, list): channel = [channel]
        cmd_str = ';'.join([':SOURCE'+str(c)+':VOLTAGE?' for c in channel])
        return [float(x) for x in self.write(cmd_str, True, len(channel)).split(";")]

    def get_offset(self, channel=None):
        if channel is None: channel = [1, 2, 3, 4]
        if not isinstance(channel, list): channel = [channel]
        cmd_str = ';'.join([':SOURCE'+str(c)+':VOLTAGE:OFFSET?' for c in channel])
        return [float(x) for x in self.write(cmd_str, True, len(channel)).split(";")]

    def get_chan_state(self, channel=None):
        if channel is None: channel = [1, 2, 3, 4]
        if not isinstance(channel, list): channel = [channel]
        cmd_str = ';'.join([':OUTPUT'+str(c)+'?' for c in channel])
        return [int(x) for x in self.write(cmd_str, True, len(channel)).split(";")]

    def set_chan_state(self, state, channel=None):
        """Set whether the channels are on or off, where 0 means off and 1 means on"""
        if channel is None: channel = [1, 2, 3, 4]
        if not isinstance(channel, list): channel = [channel]
        if not isinstance(state, list): state = [state]

        if len(state) != len(channel):
            raise ValueError("Number of channels does not match number of states.")

        cmd_str = ''
        for i in range(len(channel)):
            cmd_str = cmd_str + ';:OUTPUT'+str(channel[i])+':STATE '+str(state[i])
        print cmd_str
        self.write(cmd_str)


####################  SEQUENCER ######################

    def get_cur_waveform(self, channel=None):
        if channel is None: channel = [1, 2, 3, 4]
        if not isinstance(channel, list): channel = [channel]
        cmd_str = ';'.join([':SOURCE'+str(c)+':WAV?' for c in channel])
        return self.write(cmd_str, True, len(channel)).split(";")

    def set_cur_waveform(self, waveform_name, channel=None):
        if channel is None: channel = [1, 2, 3, 4]
        if not isinstance(channel, list): channel = [channel]
        cmd_str = ';'.join([':SOURCE'+str(c)+':WAV "'+waveform_name+'"' for c in channel])
        self.write(cmd_str)

    def set_seq_element(self, element_index, waveform_name, channel=None):
        if channel is None: channel = [1, 2, 3, 4]
        if not isinstance(channel, list): channel = [channel]
        cmd_str = ';'.join([':Sequence:ELEM'
                            +str(element_index)
                            +':WAV'+str(c)
                            +' "'
                            +waveform_name
                            +'"' for c in channel])
        self.write(cmd_str)

    def get_seq_element(self, element_index, channel=None):
        if channel is None: channel = [1, 2, 3, 4]
        if not isinstance(channel, list): channel = [channel]
        cmd_str = ';'.join([':Sequence:ELEM'+str(element_index)+':WAV'+str(c)+"?" for c in channel])
        return self.write(cmd_str, True, expected_length=len(channel)).split(";")

    def get_seq_element_loop_cnt(self, element_index):
        return self.write('SEQuence:ELEMent'+str(element_index)+':LOOP:COUNt?', True)

    def set_seq_element_loop_cnt(self, element_index, count):
        return self.write('SEQuence:ELEMent'+str(element_index)+':LOOP:COUNt '+str(count))

    def get_seq_length(self):
        return int(self.write('SEQ:LENGTH?', True, 1))

    def set_seq_length(self, length):
        self.write('SEQ:LENGTH '+str(length))

    def get_seq_element_jmp_ind(self, element_index):
        tar_type = self.get_seq_element_jmp_type(element_index)
        if tar_type == "IND":
            return self.write('SEQuence:ELEMent'+str(element_index)+':JTARget:INDex?', True, 1)
        else:
            return tar_type

    def set_seq_element_jmp_ind(self, element_index, target):
        self.set_seq_element_jmp_type(element_index, "ind")
        self.write('SEQuence:ELEMent'+str(element_index)+':JTARget:INDex '+str(target))

    def get_seq_element_jmp_type(self, element_index):
        return self.write('SEQuence:ELEMent'+str(element_index)+':JTARget:TYPE?', True, 1)

    def set_seq_element_jmp_type(self, element_index, tar_type):
        if tar_type.lower() in ["index", "ind", "next", "off"]:
            return self.write('SEQuence:ELEMent'+str(element_index)+':JTARget:TYPE '+str(tar_type))

    def get_seq_list(self):
        """Get the current list of waveforms in the sequencer"""
        seq_length = self.get_seq_length()
        seq_list = ["" for _ in range(seq_length)]

        for i in range(seq_length):
            seq_list[i] = self.get_seq_element(i+1)
        return seq_list

    def set_seq_list(self, seq_list):
        """Set the sequence list"""
        assert isinstance(seq_list, list)
        assert isinstance(seq_list[0], list)
        assert len(seq_list[0]) == 4

        seq_len = len(seq_list)

        #self.set_seq_length(0) #Delete old sequence list
        self.set_seq_length(seq_len)
        cmd_str = ""
        for i in range(seq_len):
            for k in range(4):
                cmd_str = cmd_str+';:Seq:ELEM'+str(i+1)+':WAV'+str(k+1)+' "'+seq_list[i][k]+'"'
            if i < seq_len:
                cmd_str = cmd_str+';:SEQ:ELEM'+str(i+1)+':JTAR:TYPE NEXT'
        self.settimeout(10)
        self.write(cmd_str)
        self.settimeout(.5)


import numpy as np
import sys

#These are the bit conversions needed for accurate representation on the AWG
_bit_depth_mult_offset = {8:  (254, 127),
                          12: (4094, 2047),
                          14: (16382, 8191),
                          16: (65534, 32767)}


def create_prefix(data):
    return "#"+str(len(list(str(len(data)))))+str(len(data))

def bifloat_to_uint(value, bit_depth):
    """Convert a float on the range [-1.0, 1.0] to a unsigned int.

    Not a totally straightforward conversion, this conversion will result in matching
    values seen on the AWG, however some decimals may not be represented exactly
    as certain fractions in decimal are not representable in binary.

    Args:
        value: a single float, or list of floats, or numpy array of
            floats to operate on
        bit_depth: the target AWG's bit depth, taken from the set {8, 12, 14, 16}

    Returns:
        the converted input value/list/ndarray

    Raises:
        ValueError for a bit depth outside the set of supported values.
    """
    try:
        mult, offset = _bit_depth_mult_offset[bit_depth]
    except KeyError:
        raise ValueError("No rule exists for converting a bipolar float to a bit depth of "
                         "'{}'; supported bit depths are {}."
                         .format(bit_depth, _bit_depth_mult_offset.keys()))
    # ndarray case
    if isinstance(value, np.ndarray):
        output = np.empty(value.shape, dtype=int)
        np.multiply(value, mult, output, casting='unsafe')
        output += offset
        return output

    # generic iterable case
    try:
        val_iter = iter(value)
        return [int(val*mult + offset) for val in val_iter]
    except TypeError:
        # hopefully this is a scalar
        return int(value * mult + offset)

def uint_to_bifloat(value, bit_depth):
    """Convert an unsigned int to a float on the range [-1.0, 1.0].

    This is an undo of the bifloat_to_uint function.

    Args:
        value: a single uint, or list of uints, or numpy array of
            uints to operate on
        bit_depth: the target AWG's bit depth, taken from the set {8, 12, 14, 16}

    Returns:
        the converted input value/list/ndarray

    Raises:
        ValueError for a bit depth outside the set of supported values.
    """
    try:
        mult, offset = _bit_depth_mult_offset[bit_depth]
    except KeyError:
        raise ValueError("No rule exists for converting a bipolar float to a bit depth of "
                         "'{}'; supported bit depths are {}."
                         .format(bit_depth, _bit_depth_mult_offset.keys()))
    # ndarray case
    if isinstance(value, np.ndarray):
        output = np.empty(value.shape, dtype=float)
        value = value - float(offset)
        np.divide(value, float(mult), output, casting='unsafe')
        return output

    # generic iterable case
    try:
        val_iter = iter(value)
        return [float((val- offset)/float(mult)) for val in val_iter]
    except TypeError:
        # hopefully this is a scalar
        return float((value- offset)/float(mult))



def merge_arb_and_markers(arb=None, mk1=None, mk2=None, bit_depth=14):
    """Merge arbitrary waveform and marker values into a binary array of AWG codes.

    If any of the inputs are not supplied, they will be filled with placeholder
    arrays of zeros.  This function is only set up to support 10 and 12-bit AWGs

    Args:
        arb: the arbitrary waveform data on the range [-1.0, 1.0]
        mk1, mk2: the marker data.  Can be supplied as a booleans, integers
            (0 -> off, non-zero -> on), or floats (0.0 -> off, all other values -> on)

    Returns:
        An ndarray of Tektronix-formatted AWG sample codes.

    Raises:
        ValueError if no sequences were supplied or an unsupported bit depth was
            provided.
        UnequalPatternLengths if any of the input patterns were of unequal length.
    """
    supported_bit_depths = (8, 14)
    if bit_depth not in supported_bit_depths:
        raise ValueError("Unsupported bit depth of {}; valid bit depths are {}"
                         .format(bit_depth, supported_bit_depths))
    if arb is None and mk1 is None and mk2 is None:
        raise ValueError("Must supply at least one sequence pattern to create a"
                         " merged AWG binary array.")
    if arb is not None:
        master_pat = arb
    else:
        master_pat = mk1 if mk1 is not None else mk2

    seq_len = len(master_pat)

    arb = np.zeros(seq_len, dtype=float) if arb is None else arb
    mk1 = np.zeros(seq_len, dtype=bool) if mk1 is None else mk1.astype(bool)
    mk2 = np.zeros(seq_len, dtype=bool) if mk2 is None else mk2.astype(bool)

    if len(arb) != len(mk1) or len(mk1) != len(mk2):
        raise UnequalPatternLengths("Supplied patterns of unequal length: "
                                    "len(arb) = {}, len(mk1) = {}, len(mk2) = {}"
                                    .format(len(arb), len(mk1), len(mk2)))

    # all patterns have the same length and are valid
    # convert the bipolar float to integer
    arb = bifloat_to_uint(arb, bit_depth).astype("<u2", copy=False)
    #if bit_depth == 8:
    #    np.left_shift(arb, 6, arb)

    mk1 = mk1.astype("<u2", copy=False)
    mk2 = mk2.astype("<u2", copy=False)

    # bit shift mk1 and mk2 to the correct flag bits, 15 and 16 respectively
    np.left_shift(mk1, 14, mk1)
    np.left_shift(mk2, 15, mk2)

    np.bitwise_or(arb, mk1, arb)
    np.bitwise_or(arb, mk2, arb)

    return arb

def ints_to_byte_str(codes):
    """Convert an ndarray of AWG sample codes to bytes of the proper endianness.

    Args:
        codes: ndarray of AWG sample codes

    Returns: a byte array in little-endian order.

    Raises:
        TypeError if the incoming ndarray object does not have meaningful
            endianess.
    """
    # get the endianness of the ndarray
    byte_order = codes.dtype.byteorder
    if byte_order == '=':
        # native byte order, ask the system
        byte_order = sys.byteorder
    elif byte_order == '<':
        byte_order = 'little'
    elif byte_order == '>':
        byte_order = 'big'
    else:
        raise TypeError("Got an ndarray object without meaningful endianness!")

    # if we're little-endian, return the bytes
    if byte_order == 'little':
        return codes.tobytes()
    else:
    # otherwise, byte-swap first
        return codes.byteswap().tobytes()
#.4943891
def byte_str_to_vals(codes,str_format="INT"):
    if str_format == "INT":
        vals_ints = np.fromstring(codes, dtype="<u2")
        (arb, mk1, mk2) = unmerge_arb_and_markers(vals_ints)
        return (uint_to_bifloat(arb, 14), mk1, mk2)
    elif str_format == "REAL":
        return np.fromstring(codes, dtype="<f4, <u1")

def unmerge_arb_and_markers(codes):
    seq_len = len(codes)

    arb_mask = np.zeros(seq_len, dtype="<u2")+2**14-1
    mk1_mask = np.zeros(seq_len, dtype="<u2")+2**14
    mk2_mask = np.zeros(seq_len, dtype="<u2")+2**15

    arb = np.empty(seq_len, dtype='uint16')
    mk1 = np.empty(seq_len, dtype=bool)

    mk2 = np.empty(seq_len, dtype=bool)

    np.bitwise_and(codes, arb_mask, arb)
    np.bitwise_and(codes, mk1_mask, mk1_mask)
    np.bitwise_and(codes, mk2_mask, mk2_mask)

    np.not_equal(mk1_mask, np.zeros(seq_len), mk1)
    np.not_equal(mk2_mask, np.zeros(seq_len), mk2)

    return (arb, mk1, mk2)

class UnequalPatternLengths(Exception):
    pass






