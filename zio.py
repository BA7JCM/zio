#!/usr/bin/env python
#===============================================================================
# The Star And Thank Author License (SATA)
# 
# Copyright (c) 2020 zTrix(i@ztrix.me)
# 
# Project Url: https://github.com/zTrix/zio
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software. 
# 
# And wait, the most important, you shall star/+1/like the project(s) in project url 
# section above first, and then thank the author(s) in Copyright section. 
# 
# Here are some suggested ways:
# 
#  - Email the authors a thank-you letter, and make friends with him/her/them.
#  - Report bugs or issues.
#  - Tell friends what a wonderful project this is.
#  - And, sure, you can just express thanks in your mind without telling the world.
# 
# Contributors of this project by forking have the option to add his/her name and 
# forked project url at copyright and project url sections, but shall not delete 
# or modify anything else in these two sections.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#===============================================================================

from __future__ import print_function
from __future__ import division

__version__ = "2.0.0"
__project__ = "https://github.com/zTrix/zio"

import os
import sys
import struct
import functools
import socket
import signal
import ast
import time
import errno
import select
import binascii
# for ProcessIO below
import pty
import shlex
import fcntl
import gc
import atexit
import resource
import termios
import tty
# works for python2.6 python2.7 and python3
from distutils.spawn import find_executable

# we want to keep zio as a zero-dependency single-file easy-to-use library, and even more, work across python2/python3 boundary
# https://python-future.org/compatible_idioms.html#unicode-text-string-literals

python_version_major = sys.version_info[0]      # do not use sys.version_info.major which is not available in python2.6

# python2 python3 shim
if python_version_major < 3:
    input = raw_input           # pylint: disable=undefined-variable
else:
    unicode = str
    unichr = chr

try:
    from io import BytesIO
except ImportError:
    from StringIO import StringIO as BytesIO

if True:
    # termcolor handled using bytes instead of unicode
    # if termcolor import failed, use the following v1.1.0 source code of termcolor here
    # since termcolor use MIT license, SATA license above should be OK
    ATTRIBUTES = dict( list(zip([ 'bold', 'dark', '', 'underline', 'blink', '', 'reverse', 'concealed' ], list(range(1, 9)))))
    del ATTRIBUTES['']
    HIGHLIGHTS = dict( list(zip([ 'on_grey', 'on_red', 'on_green', 'on_yellow', 'on_blue', 'on_magenta', 'on_cyan', 'on_white' ], list(range(40, 48)))))
    COLORS = dict(list(zip(['grey', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white', ], list(range(30, 38)))))
    RESET = b'\033[0m'

    def colored(text, color=None, on_color=None, attrs=None):
        fmt_str = b'\033[%dm%s'
        if color is not None: text = fmt_str % (COLORS[color], text)
        if on_color is not None: text = fmt_str % (HIGHLIGHTS[on_color], text)
        if attrs is not None:
            for attr in attrs:
                text = fmt_str % (ATTRIBUTES[attr], text)

        text += RESET
        return text

# -------------------------------------------------
# =====> packing/unpacking related functions <=====

def convert_packing(endian, bits, arg, autopad=False):
    """
    given endian, bits spec, do the following
        convert between bytes <--> int
        convert between bytes <--> [int]

    params:
        endian: < for little endian, > for big endian
        bits: bit size of packing, valid values are 8, 16, 32, 64
        arg: integer or bytes
        autopad: auto pad input string to required length if needed
    """
    pfs = {8: 'B', 16: 'H', 32: 'I', 64: 'Q'}

    if isinstance(arg, bytes):      # bytes -> int or [int]
        c = bits // 8
        r = len(arg) % c
        if r != 0:
            if autopad:
                arg = arg[:len(arg) // c * c] + (arg[-r:].ljust(c, b'\x00') if endian == '<' else arg[-r:].rjust(c, b'\x00'))
            else:
                raise ValueError('bad input length, expected multiple of %d, got %d. Fix length manually or use autopad=True' % (c, len(arg)))
        unpacked = struct.unpack(endian + pfs[bits] * (len(arg) // c), arg)
        return list(unpacked) if len(unpacked) > 1 else unpacked[0]
    else:                           # int or [int] -> bytes
        args = list(arg) if isinstance(arg, (list, tuple)) else [arg]
        return struct.pack(endian + pfs[bits] * len(args), *args)

l8 = functools.partial(convert_packing, '<', 8)
b8 = functools.partial(convert_packing, '>', 8)
l16 = functools.partial(convert_packing, '<', 16)
b16 = functools.partial(convert_packing, '>', 16)
l32 = functools.partial(convert_packing, '<', 32)
b32 = functools.partial(convert_packing, '>', 32)
l64 = functools.partial(convert_packing, '<', 64)
b64 = functools.partial(convert_packing, '>', 64)

# -------------------------------------------------
# =====> utility functions <=====

def bytes2hex(s):
    '''
    Union{bytes, unicode} -> bytes
    '''
    if isinstance(s, unicode):
        s = s.encode()
    return binascii.hexlify(s)

def hex2bytes(s, autopad=False):
    '''
    bytes -> bytes
    '''
    if isinstance(s, unicode):
        s = s.encode()
    s = s.strip()
    if len(s) % 2 == 1:
        if autopad == 'left' or autopad == True:
            s = b'0' + s
        elif autopad == 'right':
            s = s + b'0'
        else:
            raise ValueError('invalid length of hex bytes: %d, should be multiple of 2. Use autopad=True to fix automatically' % len(s))
    return binascii.unhexlify(s)

tohex = bytes2hex
unhex = hex2bytes

if python_version_major < 3:
    def xor(a, b):
        '''
        bytes -> bytes -> bytes
        the first param a must be longer than or equal to the length of the second param
        '''
        return b''.join([chr(ord(c) ^ ord(b[i % len(b)])) for i, c in enumerate(a)])
else:
    def xor(a, b):
        '''
        bytes -> bytes -> bytes
        the first param a must be longer than or equal to the length of the second param
        '''
        return bytes([c ^ b[i % len(b)] for i, c in enumerate(a)])

def is_hostport_tuple(target):
    return type(target) == tuple and len(target) == 2 and isinstance(target[1], int) and target[1] >= 0 and target[1] < 65536

def match_pattern(pattern, byte_buf):
    '''
    pattern -> byte_buf -> index span # (-1, -1) for not found)
    pattern could be bytes or re objects or lambda function which returns index span
    '''
    if isinstance(pattern, bytes):
        i = byte_buf.find(pattern)
        if i > -1:
            return (i, i + len(pattern))
        else:
            return (-1, -1)
    elif hasattr(pattern, 'match') and hasattr(pattern, 'search'):
        mo = pattern.search(byte_buf)
        if not mo:
            return (-1, -1)
        else:
            return mo.span()
    elif callable(pattern):
        return pattern(byte_buf)

def write_stdout(data):
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout.buffer.write(data)
    else:
        if python_version_major < 3:
            sys.stdout.write(data)
        else:
            sys.stdout.write(data.decode())
    sys.stdout.flush()

def write_stderr(data):
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr.buffer.write(data)
    else:
        if python_version_major < 3:
            sys.stderr.write(data)
        else:
            sys.stderr.write(data.decode())
    sys.stderr.flush()

# -------------------------------------------------
# =====> zio class modes and params <=====

PIPE = 'pipe'           # io mode (process io): send all characters untouched, but use PIPE, so libc cache may apply
TTY = 'tty'             # io mode (process io): normal tty behavier, support Ctrl-C to terminate, and auto \r\n to display more readable lines for human
TTY_RAW = 'ttyraw'      # io mode (process io): send all characters just untouched

def COLORED(f, color='cyan', on_color=None, attrs=None):
    return lambda s : colored(f(s), color, on_color, attrs)

# read/write transform functions
# bytes -> (printable) bytes
if python_version_major < 3:
    def REPR(s): return b'b' + repr(s) + b'\r\n'
else:
    def REPR(s): return str(s).encode() + b'\r\n'

def EVAL(s):    # now you are not worried about pwning yourself, do not use ast.literal_eval because of 1. encoding issue 2. we only eval string
    st = 0      # 0 for normal, 1 for escape, 2 for \xXX
    ret = []
    i = 0
    while i < len(s):
        c = s[i:i+1]    # current byte, for python2/3 compatibility
        if st == 0:
            if c == b'\\':
                st = 1
            else:
                ret.append(c)
        elif st == 1:
            if c in (b'"', b"'", b"\\", b"t", b"n", b"r"):
                if c == b't':
                    ret.append(b'\t')
                elif c == b'n':
                    ret.append(b'\n')
                elif c == b'r':
                    ret.append(b'\r')
                else:
                    ret.append(c)
                st = 0
            elif c == b'x':
                st = 2
            else:
                raise ValueError('invalid repr of str %s' % s)
        else:
            num = int(s[i:i+2], 16)
            assert 0 <= num < 256
            if python_version_major < 3:
                ret.append(chr(num))
            else:
                ret.append(bytes([num]))
            st = 0
            i += 1
        i += 1
    return b''.join(ret)

def HEX(s): return bytes2hex(s) + b'\r\n'
TOHEX = HEX
def UNHEX(s): return hex2bytes(s)

if python_version_major < 3:
    def BIN(s): return b' '.join([format(ord(x),'08b') for x in str(s)]) + b'\r\n'
else:
    def BIN(s): return b' '.join([format(x,'08b').encode() for x in s]) + b'\r\n'

def UNBIN(s, autopad=False):
    s = bytes(filter(lambda x: x in b'01', s))
    if len(s) % 8 != 0:
        extra = 8 - len(s) % 8
        if autopad == 'left' or autopad == True:
            s = (b'0' * extra) + s
        elif autopad == 'right':
            s = s + (b'0' * extra)
        else:
            raise ValueError('invalid length of 01 bytestring: %d, should be multiple of 8. Use autopad=True to fix automatically' % len(s))
    if python_version_major < 3:
        return b''.join([chr(int(s[x:x+8],2)) for x in range(0, len(s), 8)])
    else:
        return bytes([int(s[x:x+8],2) for x in range(0, len(s), 8)])

def RAW(s): return s
def NONE(s): return b''

# -------------------------------------------------
# =====> zio helper functions <=====

def select_ignoring_useless_signal(iwtd, owtd, ewtd, timeout=None):
    '''This is a wrapper around select.select() that ignores signals. If
    select.select raises a select.error exception and errno is an EINTR
    error then it is ignored. Mainly this is used to ignore sigwinch
    (terminal resize). '''

    # if select() is interrupted by a signal (errno==EINTR) then
    # we loop back and enter the select() again.
    if timeout is not None:
        end_time = time.time() + timeout
    while True:
        try:
            return select.select(iwtd, owtd, ewtd, timeout)
        except select.error:
            err = sys.exc_info()[1]
            if err[0] == errno.EINTR:
                # if we loop back we have to subtract the
                # amount of time we already waited.
                if timeout is not None:
                    timeout = end_time - time.time()
                    if timeout < 0:
                        return([], [], [])
            else:
                # something else caused the select.error, so
                # this actually is an exception.
                raise

# zio class here
class zio(object):
    '''
    zio: unified io interface for both socket io and process io
    '''
    
    def __init__(self, target,
        # common params
        timeout=None,
        logfile=None,
        print_read=True,
        print_write=True,
        debug=None,
        # ProcessIO params 
        stdin=PIPE,
        stdout=TTY_RAW,
        cwd=None,
        env=None,
        sighup=signal.SIG_DFL,
        write_delay=0.05,
    ):
        """
        zio is an easy-to-use io library for pwning development, supporting an unified interface for local process pwning and remote tcp socket io
        note that zio fully operates at bytes level instead of unicode, so remember to use bytes when passing arguments to zio methods

        example:

        io = zio(('localhost', 80), print_read=COLORED(RAW, 'yellow'), print_write=HEX)
        io = zio(socket.create_connection(('127.0.0.1', 80)))

        io = zio('ls -l')
        io = zio(['ls', '-l'])

        params:
            print_read = bool, if true, print all the data read from target
            print_write = bool, if true, print all the data sent out
        """

        if not target:
            raise ValueError('cmdline or socket not provided for zio, try zio("ls -l")')

        self.target = target
        self.print_read = print_read
        self.print_write = print_write
        if logfile is None:
            self.logfile = sys.stderr
        else:
            self.logfile = logfile  # must be opened using 'rb'

        # zio object itself is a buffered reader/writer
        self.buffer = bytearray()

        self.debug = debug

        if isinstance(timeout, int) and timeout > 0:
            self.timeout = timeout
        else:
            self.timeout = 16

        if is_hostport_tuple(self.target) or isinstance(self.target, socket.socket):
            self.io = SocketIO(self.target, timeout=self.timeout)
        else:
            self.io = ProcessIO(self.target, timeout=self.timeout,
                stdin=stdin,
                stdout=stdout,
                cwd=cwd,
                env=env,
                sighup=sighup,
                write_delay=write_delay,
                )

    def log_read(self, byte_buf):
        '''
        bytes -> IO bytes
        '''
        if self.print_read:
            content = self.read_transform(byte_buf)
            if hasattr(self.logfile, 'buffer'):
                self.logfile.buffer.write(content)
            else:
                self.logfile.write(content)
            self.logfile.flush()

    def log_write(self, byte_buf):
        '''
        bytes -> IO bytes
        '''
        if self.print_write:
            content = self.write_transform(byte_buf)
            if hasattr(self.logfile, 'buffer'):
                self.logfile.buffer.write(content)
            else:
                self.logfile.write(content)
            self.logfile.flush()

    @property
    def print_read(self):
        return self.read_transform is not None and self.read_transform is not NONE

    @print_read.setter
    def print_read(self, value):
        if value == True:
            self.read_transform = RAW
        elif value == False:
            self.read_transform = NONE
        elif callable(value):
            self.read_transform = value
        else:
            raise ValueError('bad print_read value')
        
        assert callable(self.read_transform)

    @property
    def print_write(self):
        return self.write_transform is not None and self.write_transform is not NONE

    @print_write.setter
    def print_write(self, value):
        if value == True:
            self.write_transform = RAW
        elif value == False:
            self.write_transform = NONE
        elif callable(value):
            self.write_transform = value
        else:
            raise ValueError('bad print_read value')
        
        assert callable(self.write_transform)

    def read(self, size=None):
        '''
        if size is -1 or None, then read all bytes available until EOF
        if size is a positive integer, read exactly `size` bytes and return
        raise EOFError if EOF occurred before full size read
        '''
        is_read_all = size is None or size < 0
        while True:
            if is_read_all or len(self.buffer) < size:
                incoming = self.io.recv(1536)
                if incoming is None:
                    if is_read_all:
                        ret = bytes(self.buffer)
                        # self.buffer.clear()   # note: python2 does not support bytearray.clear()
                        self.buffer = bytearray()
                        self.log_read(ret)
                        return ret
                    else:
                        raise EOFError('EOF occured before full size read, buffer = %s' % self.buffer)
                self.buffer.extend(incoming)

            if not is_read_all and len(self.buffer) >= size:
                ret = bytes(self.buffer[:size])
                self.buffer = self.buffer[size:]
                self.log_read(ret)
                return ret

    read_exact = read

    def read_to_end(self):
        return self.read(size=-1)

    def read_line(self, keep=True):
        content = self.read_until(b'\n', keep=True)
        if not keep:
            content = content.rstrip(b'\r\n')
        return content

    readline = read_line
    recvline = read_line    # for pwntools compatibility

    def read_until(self, pattern, keep=True):
        '''
        read until some bytes pattern found
        patter could be one of following:
        1. bytes
        2. re object(must compile using bytes rather than unicode, e.g: re.compile(b"something"))
        3. callable functions return True for found and False for not found
        4. lists of things above

        raise EOFError if EOF occurred before pattern found
        '''

        if not isinstance(pattern, (list, tuple)):
            pattern_list = [pattern]
        else:
            pattern_list = pattern

        while True:
            for p in pattern_list:
                span = match_pattern(p, self.buffer)
                if span[0] > -1: # found
                    ret = self.buffer[:span[1]] if keep == True else self.buffer[:span[0]]
                    self.log_read(self.buffer[:span[1]])
                    self.buffer = self.buffer[span[1]:]
                    return ret

            incoming = self.io.recv(1536)
            if incoming is None:
                raise EOFError('EOF occured before pattern match, buffer = %s' % self.buffer)

            self.buffer.extend(incoming)

    readuntil = read_until
    recv_until = read_until
    recvuntil = read_until

    def read_some(self, size=None):
        '''
        just read 1 or more available bytes (less than size) and return
        '''
        return self.io.recv(size)

    recv = read_some

    def read_until_timeout(self, timeout=1):
        '''
        read for some timeout, return current buffer plus whatever read
        '''
        end_time = time.time() + timeout

        while True:
            r, _w, _e = select_ignoring_useless_signal([self.io.rfd], [], [], timeout)
            data = None
            if self.io.rfd in r:
                data = self.io.recv(1536)
                if data is None:
                    break
                elif data:
                    self.buffer.extend(data)
                    break

            timeout = end_time - time.time()
            if timeout < 0:
                break

        if len(self.buffer):
            ret = bytes(self.buffer)
            self.log_read(ret)
            self.buffer = bytearray()
            return ret
        return b''

    read_eager = read_until_timeout

    def readable(self):
        '''
        tell wether we have some data to read
        '''
        return select_ignoring_useless_signal([self.io.rfd], [], [], 0) == ([self.io.rfd], [], [])

    def write(self, byte_buf):
        '''
        write/sendall bytes and flush them all
        '''
        if not byte_buf:
            return 0
        self.log_write(byte_buf)
        self.io.send(byte_buf)
        return len(byte_buf)

    send = write    # for pwntools compatibility

    def write_line(self, byte_buf):
        '''
        write byte_buf and a linesep
        '''
        return self.write(byte_buf + os.linesep.encode())

    sendline = write_line
    send_line = write_line
    writeline = write_line

    def write_lines(self, sequence):
        n = 0
        for s in sequence:
            n += self.write_line(s)
        return n

    writelines = write_lines

    def write_after(self, pattern, byte_buf):
        self.read_until(pattern)
        self.write(byte_buf)

    writeafter = write_after
    sendafter = write_after

    def write_line_after(self, pattern, byte_buf):
        self.read_until(pattern)
        self.writeline(byte_buf)

    writeline_after = write_line_after  # for human mistake
    sendline_after = write_line_after   # for human mistake
    sendlineafter = write_line_after    # for pwntools compatibility

    def send_eof(self):
        '''
        notify peer that we have done writing
        '''
        self.io.send_eof()

    def interact(self, read_transform=None, write_transform=None):
        '''
        interact with current tty stdin/stdout
        '''
        self.io.interact(read_transform=read_transform, write_transform=write_transform)

    interactive = interact      # for pwntools compatibility

    def close(self):
        '''
        close underlying io and free all resources
        '''
        self.io.close()

    def is_closed(self):
        '''
        tell whether this zio object is closed
        '''
        return self.io.is_closed()

    def is_eof_seen(self):
        '''
        tell whether we have received EOF from peer end
        '''
        return self.io.eof_seen

    def is_eof_sent(self):
        '''
        tell whether we have sent EOF to the peer 
        '''
        return self.io.eof_sent

    def flush(self):
        '''
        kept to act like a file-like object
        '''
        pass

    def fileno(self):
        '''
        return underlying os fileno, act like a file-like object
        '''
        return self.io.rfd

    def mode(self):
        return self.io.mode

    def __str__(self):
        return '<zio target=%s, timeout=%s, io=%s, buffer=%s>' % (self.target, self.timeout, str(self.io), self.buffer)

class SocketIO:
    mode = 'socket'

    def __init__(self, target, timeout=None):
        self.timeout = timeout
        if isinstance(target, socket.socket):
            self.sock = target
        else:
            self.sock = socket.create_connection(target, self.timeout)

        self.eof_seen = False
        self.eof_sent = False

    @property
    def rfd(self):
        return self.sock.fileno()

    @property
    def wfd(self):
        return self.sock.fileno()

    def recv(self, size=None):
        '''
        recv 1 or more available bytes then return
        return None to indicate EOF
        since we use b'' to indicate empty string in case of timeout, so do not return b'' for EOF
        '''
        b = self.sock.recv(size)
        if not b:
            self.eof_seen = True
            return None
        return b

    def send(self, buf):
        return self.sock.sendall(buf)

    def send_eof(self):
        self.eof_sent = True
        self.sock.shutdown(socket.SHUT_WR)

    def interact(self, read_transform=None, write_transform=None):
        while not self.is_closed():
            try:
                r, _w, _e = select_ignoring_useless_signal([self.rfd, pty.STDIN_FILENO], [], [])
            except KeyboardInterrupt:
                break
            data = None
            if self.rfd in r:
                data = self.recv(1024)
                if data:
                    if read_transform is not None:
                        data = read_transform(data)
                    write_stdout(data)
                else:       # EOF
                    self.eof_seen = True
                    break
            if pty.STDIN_FILENO in r:
                try:
                    data = os.read(pty.STDIN_FILENO, 1024)
                except OSError as e:
                    # the subprocess may have closed before we get to reading it
                    if e.errno != errno.EIO:
                        raise
                if data:
                    if write_transform:
                        data = write_transform(data)
                    self.send(data)

    def close(self):
        self.eof_seen = True
        self.eof_sent = True
        self.sock.close()

    def is_closed(self):
        if python_version_major < 3:
            return isinstance(self.sock._sock, socket._closedsocket)    # pylint: disable=no-member
        else:
            return self.sock._closed

    def __str__(self):
        return '<SocketIO ' \
            + 'self.sock=' + repr(self.sock) \
            + '>'

    def __repr__(self):
        return repr(self.sock)

class ProcessIO:
    mode = 'process'

    def __init__(self, target, timeout=None, stdin=PIPE, stdout=TTY_RAW, cwd=None, env=None, sighup=None, write_delay=None):
        if os.name == 'nt':
            raise RuntimeError("zio (version %s) process mode does not support windows operation system." % __version__)

        self.timeout = timeout

        self.write_delay = write_delay  # the delay before writing data, pexcept said Linux don't like this to be below 30ms
        self.close_delay = 0.1          # like pexcept, will used by close(), to give kernel time to update process status, time in seconds
        self.terminate_delay = 0.1      # like close_delay

        self.exit_code = None
        self.pid = None

        self.eof_seen = False
        self.eof_sent = False

        # STEP 1: prepare command line args
        if isinstance(target, type('')):
            self.args = shlex.split(target)
        else:
            self.args = list(target)

        executable = find_executable(self.args[0])
        if not executable:
            raise ValueError('unable to find executable in path: %s' % self.args)

        if not os.access(executable, os.X_OK):
            raise RuntimeError('could not execute file without X bit set, please chmod +x %s' % executable)

        self.args[0] = executable

        # STEP 2: create pipes
        stdout_master_fd, stdout_slave_fd = self._pipe_cloexec() if stdout == PIPE else pty.openpty()

        if stdout_master_fd < 0 or stdout_slave_fd < 0:
            raise RuntimeError('Could not create pipe or openpty for stdout/stderr')

        # use another pty for stdin because we don't want our input to be echoed back in stdout
        # set echo off does not help because in application like ssh, when you input the password
        # echo will be switched on again
        # and dont use os.pipe either, because many thing weired will happen, such as baskspace not working, ssh lftp command hang

        stdin_master_fd, stdin_slave_fd = self._pipe_cloexec() if stdin == PIPE else pty.openpty()

        if stdin_master_fd < 0 or stdin_slave_fd < 0:
            raise RuntimeError('Could not openpty for stdin')

        # STEP 3: fork and start engine

        gc_enabled = gc.isenabled()
        # Disable gc to avoid bug where gc -> file_dealloc ->
        # write to stderr -> hang.  http://bugs.python.org/issue1336
        gc.disable()
        try:
            self.pid = os.fork()
        except:
            if gc_enabled:
                gc.enable()
            raise

        if self.pid < 0:
            raise RuntimeError('failed to fork')
        elif self.pid == 0:     # Child
            os.close(stdout_master_fd)

            if os.isatty(stdin_slave_fd):
                self.__pty_make_controlling_tty(stdin_slave_fd)
                # self.__pty_make_controlling_tty(stdout_slave_fd)

            try:
                if os.isatty(stdout_slave_fd) and os.isatty(pty.STDIN_FILENO):
                    h, w = self._getwinsize(0)
                    self._setwinsize(stdout_slave_fd, h, w)     # note that this may not be successful
            except BaseException as ex:
                print('[ WARN ] setwinsize exception: %s' % (str(ex)), file=sys.stderr)

            # Dup fds for child
            def _dup2(a, b):
                # dup2() removes the CLOEXEC flag but
                # we must do it ourselves if dup2()
                # would be a no-op (issue #10806).
                if a == b:
                    self._set_cloexec_flag(a, False)
                elif a is not None:
                    os.dup2(a, b)

            # redirect stdout and stderr to pty
            os.dup2(stdout_slave_fd, pty.STDOUT_FILENO)
            os.dup2(stdout_slave_fd, pty.STDERR_FILENO)

            # redirect stdin to stdin_slave_fd instead of stdout_slave_fd, to prevent input echoed back
            _dup2(stdin_slave_fd, pty.STDIN_FILENO)

            if stdout_slave_fd > 2:
                os.close(stdout_slave_fd)

            if stdin_master_fd is not None:
                os.close(stdin_master_fd)

            # do not allow child to inherit open file descriptors from parent

            max_fd = resource.getrlimit(resource.RLIMIT_NOFILE)[0]
            os.closerange(3, max_fd)

            # the following line matters, for example, if SIG_DFL specified and sighup sent when exit, the exitcode of child process can be affected to 1
            if sighup is not None:
                # note that, self.signal could only be one of (SIG_IGN, SIG_DFL)
                signal.signal(signal.SIGHUP, sighup)

            if cwd is not None:
                os.chdir(cwd)
            
            if env is None:
                os.execv(executable, self.args)
            else:
                os.execvpe(executable, self.args, env)

            # TODO: add subprocess errpipe to detect child error
            # child exit here, the same as subprocess module do
            os._exit(255)

        else:
            # after fork, parent
            self.wfd = stdin_master_fd
            self.rfd = stdout_master_fd

            if os.isatty(self.wfd):
                # there is no way to eliminate controlling characters in tcattr
                # so we have to set raw mode here now
                self._wfd_init_mode = tty.tcgetattr(self.wfd)[:]
                if stdin == TTY_RAW:
                    self._ttyraw(self.wfd)
                    self._wfd_raw_mode = tty.tcgetattr(self.wfd)[:]
                else:
                    self._wfd_raw_mode = self._wfd_init_mode[:]

            if os.isatty(self.rfd):
                self._rfd_init_mode = tty.tcgetattr(self.rfd)[:]
                if stdout == TTY_RAW:
                    self._ttyraw(self.rfd, raw_in = False, raw_out = True)
                    self._rfd_raw_mode = tty.tcgetattr(self.rfd)[:]
                    # if self.debug: log('stdout tty raw mode: %r' % self._rfd_raw_mode, f = self.debug)
                else:
                    self._rfd_raw_mode = self._rfd_init_mode[:]

            os.close(stdin_slave_fd)
            os.close(stdout_slave_fd)
            if gc_enabled:
                gc.enable()

            time.sleep(self.close_delay)

            atexit.register(self._kill, signal.SIGHUP)

    def recv(self, size=None):
        '''
        recv 1 or more available bytes then return
        return None to indicate EOF
        since we use b'' to indicate empty string in case of timeout, so do not return b'' for EOF
        '''
        b = os.read(self.rfd, size)
        # https://docs.python.org/3/library/os.html#os.read
        # If the end of the file referred to by fd has been reached, an empty bytes object is returned.
        if not b:
            self.eof_seen = True
            return None
        return b

    def send(self, buf, delay=True):
        if delay:       # prevent write too fast
            time.sleep(self.write_delay)
        return os.write(self.wfd, buf)

    def send_eof(self, force_close=False):
        self.eof_sent = True

        if not os.isatty(self.wfd):     # pipes can be closed harmlessly
            os.close(self.wfd)

        # for pty, close master fd in Mac won't cause slave fd input/output error, so let's do it!
        elif sys.platform.startswith('darwin'):
            os.close(self.wfd)
        else:       # assume Linux here
            # according to http://linux.die.net/man/3/cfmakeraw
            # set min = 0 and time > 0, will cause read timeout and return 0 to indicate EOF
            # but the tricky thing here is, if child read is invoked before this
            # it will still block forever, so you have to call send_eof before that happens
            mode = tty.tcgetattr(self.wfd)[:]
            mode[tty.CC][tty.VMIN] = 0
            mode[tty.CC][tty.VTIME] = 1
            tty.tcsetattr(self.wfd, tty.TCSAFLUSH, mode)
            if force_close:
                time.sleep(self.close_delay)
                os.close(self.wfd)  # might cause EIO (input/output error)! use force_close at your own risk

    def interact(self, read_transform=None, write_transform=None):
        """
        when stdin is passed using os.pipe, backspace key will not work as expected,
        if wfd is not a tty, then when backspace pressed, I can see that 0x7f is passed, but vim does not delete backwards, so you should choose the right input when using zio
        """
        # if input_filter is not none, we should let user do some line editing
        if os.isatty(pty.STDIN_FILENO):
            mode = tty.tcgetattr(pty.STDIN_FILENO)  # mode will be restored after interact
            self._ttyraw(pty.STDIN_FILENO)           # set to raw mode to pass all input thru, supporting apps as vim
        if os.isatty(self.wfd):
            # here, enable cooked mode for process stdin
            # but we should only enable for those who need cooked mode, not stuff like vim
            # we just do a simple detection here
            wfd_mode = tty.tcgetattr(self.wfd)
            # if self.debug:
            #     log('wfd now mode = ' + repr(wfd_mode), f = self.debug)
            #     log('wfd raw mode = ' + repr(self._wfd_raw_mode), f = self.debug)
            #     log('wfd ini mode = ' + repr(self._wfd_init_mode), f = self.debug)
            if wfd_mode == self._wfd_raw_mode:     # if untouched by forked child
                tty.tcsetattr(self.wfd, tty.TCSAFLUSH, self._wfd_init_mode)
                # if self.debug:
                #     log('change wfd back to init mode', f = self.debug)
            # but wait, things here are far more complex than that
            # most applications set mode not by setting it to some value, but by flipping some bits in the flags
            # so, if we set wfd raw mode at the beginning, we are unable to set the correct mode here
            # to solve this situation, set stdin = TTY_RAW, but note that you will need to manually escape control characters by prefixing Ctrl-V

        try:
            rfdlist = [self.rfd, pty.STDIN_FILENO]
            if os.isatty(self.wfd):
                # wfd for tty echo
                rfdlist.append(self.wfd)
            while self._isalive():
                if len(rfdlist) == 0:
                    break
                if self.rfd not in rfdlist:
                    break
                try:
                    r, _w, _e = select_ignoring_useless_signal(rfdlist, [], [])
                except KeyboardInterrupt:
                    break
                # if self.debug: log('r  = ' + repr(r), f = self.debug)
                if self.wfd in r:          # handle tty echo back first if wfd is a tty
                    try:
                        data = None
                        data = os.read(self.wfd, 1024)
                    except OSError as e:
                        if e.errno != errno.EIO:
                            raise
                    if data:
                        write_stdout(data)
                    else:
                        rfdlist.remove(self.wfd)
                if self.rfd in r:
                    try:
                        data = None
                        data = os.read(self.rfd, 1024)
                    except OSError as e:
                        if e.errno != errno.EIO:
                            raise
                    if data:
                        if read_transform:
                            data = read_transform(data)
                        # now we are in interact mode, so users want to see things in real
                        write_stdout(data)
                    else:
                        rfdlist.remove(self.rfd)
                        self.eof_seen = True
                if pty.STDIN_FILENO in r:
                    try:
                        data = None
                        data = os.read(pty.STDIN_FILENO, 1024)
                    except OSError as e:
                        # the subprocess may have closed before we get to reading it
                        if e.errno != errno.EIO:
                            raise
                    # if self.debug and os.isatty(self.wfd):
                    #     wfd_mode = tty.tcgetattr(self.wfd)
                    #     log('stdin wfd mode = ' + repr(wfd_mode), f = self.debug)
                    # in BSD, you can still read '' from rfd, so never use `data is not None` here
                    if data:
                        if write_transform:
                            data = write_transform(data)
                        if not os.isatty(self.wfd):     # we must do the translation when tty does not help
                            data = data.replace(b'\r', b'\n')
                            # also echo back by ourselves, now we are echoing things we input by hand, so there is no need to wrap with print_write by default, unless raw_rw set to False
                            write_stdout(data)
                        while data != b'' and self._isalive():
                            n = self.send(data, delay=False)
                            data = data[n:]
                    else:
                        self.send_eof(force_close=True)
                        rfdlist.remove(pty.STDIN_FILENO)

            while True:     # read the final buffered output, note that the process probably is not alive, so use while True to read until end (fix pipe stdout interact mode bug)
                r, _w, _e = select_ignoring_useless_signal([self.rfd], [], [], timeout=self.close_delay)
                if self.rfd in r:
                    try:
                        data = None
                        data = os.read(self.rfd, 1024)
                    except OSError as e:
                        if e.errno != errno.EIO:
                            raise
                    # in BSD, you can still read '' from rfd, so never use `data is not None` here
                    if data:
                        if read_transform:
                            data = read_transform(data)
                        write_stdout(data)
                    else:
                        self.eof_seen = True
                        break
                else:
                    break
        finally:
            if os.isatty(pty.STDIN_FILENO):
                tty.tcsetattr(pty.STDIN_FILENO, tty.TCSAFLUSH, mode)
            if os.isatty(self.wfd):
                self._ttyraw(self.wfd)

    def close(self, force_close=True):
        '''
        close and clean up, nothing can and should be done after closing
        '''
        if self.is_closed():
            return
        try:
            os.close(self.wfd)
        except:
            pass    # may already closed in write_eof
        os.close(self.rfd)
        time.sleep(self.close_delay)
        if self._isalive():
            if not self._terminate(force_close):
                raise RuntimeError('Could not terminate child process')
        self.eof_seen = True
        self.eof_sent = True
        self.rfd = -1
        self.wfd = -1

    def is_closed(self):
        return self.rfd == -1 and self.wfd == -1 and self.eof_sent == True and self.eof_seen == True

    def __str__(self):
        return '<ProcessIO cmdline=%s>' % (self.args)

    # ---- internal methods ----

    def _kill(self, sig):

        '''This sends the given signal to the child application. In keeping
        with UNIX tradition it has a misleading name. It does not necessarily
        kill the child unless you send the right signal. '''

        # Same as os.kill, but the pid is given for you.
        if self._isalive() and self.pid > 0:
            os.kill(self.pid, sig)

    def _terminate(self, force=False):

        '''This forces a child process to terminate. It starts nicely with
        SIGHUP and SIGINT. If "force" is True then moves onto SIGKILL. This
        returns True if the child was terminated. This returns False if the
        child could not be terminated. '''

        if not self._isalive():
            return True
        try:
            self._kill(signal.SIGHUP)
            time.sleep(self.terminate_delay)
            if not self._isalive():
                return True
            self._kill(signal.SIGCONT)
            time.sleep(self.terminate_delay)
            if not self._isalive():
                return True
            self._kill(signal.SIGINT)        # SIGTERM is nearly identical to SIGINT
            time.sleep(self.terminate_delay)
            if not self._isalive():
                return True
            if force:
                self._kill(signal.SIGKILL)
                time.sleep(self.terminate_delay)
                if not self._isalive():
                    return True
                else:
                    return False
            return False
        except OSError:
            # I think there are kernel timing issues that sometimes cause
            # this to happen. I think isalive() reports True, but the
            # process is dead to the kernel.
            # Make one last attempt to see if the kernel is up to date.
            time.sleep(self.terminate_delay)
            if not self._isalive():
                return True
            else:
                return False

    def _wait(self):

        '''This waits until the child exits. This is a blocking call. This will
        not read any data from the child, so this will block forever if the
        child has unread output and has terminated. In other words, the child
        may have printed output then called exit(), but, the child is
        technically still alive until its output is read by the parent. '''

        if self._isalive():
            _pid, status = os.waitpid(self.pid, 0)
        else:
            raise Exception('Cannot wait for dead child process.')
        self.exit_code = os.WEXITSTATUS(status)
        if os.WIFEXITED(status):
            self.exit_code = os.WEXITSTATUS(status)
        elif os.WIFSIGNALED(status):
            self.exit_code = os.WTERMSIG(status)
        elif os.WIFSTOPPED(status):
            # You can't call wait() on a child process in the stopped state.
            raise RuntimeError('Called wait() on a stopped child ' +
                    'process. This is not supported. Is some other ' +
                    'process attempting job control with our child pid?')
        return self.exit_code

    def _isalive(self):

        '''This tests if the child process is running or not. This is
        non-blocking. If the child was terminated then this will read the
        exit code or signalstatus of the child. This returns True if the child
        process appears to be running or False if not. It can take literally
        SECONDS for Solaris to return the right status. '''

        if self.exit_code is not None:
            return False

        if self.eof_seen:
            # This is for Linux, which requires the blocking form
            # of waitpid to # get status of a defunct process.
            # This is super-lame. The flag_eof would have been set
            # in read_nonblocking(), so this should be safe.
            waitpid_options = 0
        else:
            waitpid_options = os.WNOHANG

        try:
            pid, status = os.waitpid(self.pid, waitpid_options)
        except OSError:
            err = sys.exc_info()[1]
            # No child processes
            if err.errno == errno.ECHILD:
                raise RuntimeError('isalive() encountered condition ' +
                        'where "terminated" is 0, but there was no child ' +
                        'process. Did someone else call waitpid() ' +
                        'on our process?')
            else:
                raise err

        # I have to do this twice for Solaris.
        # I can't even believe that I figured this out...
        # If waitpid() returns 0 it means that no child process
        # wishes to report, and the value of status is undefined.
        if pid == 0:
            try:
                ### os.WNOHANG) # Solaris!
                pid, status = os.waitpid(self.pid, waitpid_options)
            except OSError as e:
                # This should never happen...
                if e.errno == errno.ECHILD:
                    raise RuntimeError('isalive() encountered condition ' +
                            'that should never happen. There was no child ' +
                            'process. Did someone else call waitpid() ' +
                            'on our process?')
                else:
                    raise

            # If pid is still 0 after two calls to waitpid() then the process
            # really is alive. This seems to work on all platforms, except for
            # Irix which seems to require a blocking call on waitpid or select,
            # so I let read_nonblocking take care of this situation
            # (unfortunately, this requires waiting through the timeout).
            if pid == 0:
                return True

        if pid == 0:
            return True

        if os.WIFEXITED(status):
            self.exit_code = os.WEXITSTATUS(status)
        elif os.WIFSIGNALED(status):
            self.exit_code = os.WTERMSIG(status)
        elif os.WIFSTOPPED(status):
            raise RuntimeError('isalive() encountered condition ' +
                    'where child process is stopped. This is not ' +
                    'supported. Is some other process attempting ' +
                    'job control with our child pid?')
        return False

    def __pty_make_controlling_tty(self, tty_fd):
        '''This makes the pseudo-terminal the controlling tty. This should be
        more portable than the pty.fork() function. Specifically, this should
        work on Solaris. '''

        child_name = os.ttyname(tty_fd)

        # Disconnect from controlling tty. Harmless if not already connected.
        try:
            fd = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
            if fd >= 0:
                os.close(fd)
        # which exception, shouldnt' we catch explicitly .. ?
        except:
            # Already disconnected. This happens if running inside cron.
            pass

        os.setsid()

        # Verify we are disconnected from controlling tty
        # by attempting to open it again.
        try:
            fd = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
            if fd >= 0:
                os.close(fd)
                raise Exception('Failed to disconnect from ' +
                    'controlling tty. It is still possible to open /dev/tty.')
        # which exception, shouldnt' we catch explicitly .. ?
        except:
            # Good! We are disconnected from a controlling tty.
            pass

        # Verify we can open child pty.
        fd = os.open(child_name, os.O_RDWR)
        if fd < 0:
            raise Exception("Could not open child pty, " + child_name)
        else:
            os.close(fd)

        # Verify we now have a controlling tty.
        fd = os.open("/dev/tty", os.O_WRONLY)
        if fd < 0:
            raise Exception("Could not open controlling tty, /dev/tty")
        else:
            os.close(fd)

    def _set_cloexec_flag(self, fd, cloexec=True):
        try:
            cloexec_flag = fcntl.FD_CLOEXEC
        except AttributeError:
            cloexec_flag = 1

        old = fcntl.fcntl(fd, fcntl.F_GETFD)
        if cloexec:
            fcntl.fcntl(fd, fcntl.F_SETFD, old | cloexec_flag)
        else:
            fcntl.fcntl(fd, fcntl.F_SETFD, old & ~cloexec_flag)

    def _pipe_cloexec(self):
        """Create a pipe with FDs set CLOEXEC."""
        # Pipes' FDs are set CLOEXEC by default because we don't want them
        # to be inherited by other subprocesses: the CLOEXEC flag is removed
        # from the child's FDs by _dup2(), between fork() and exec().
        # This is not atomic: we would need the pipe2() syscall for that.
        r, w = os.pipe()
        self._set_cloexec_flag(r)
        self._set_cloexec_flag(w)
        return w, r

    def _setwinsize(self, fd, rows, cols):   # from pexpect, thanks!

        '''This sets the terminal window size of the child tty. This will cause
        a SIGWINCH signal to be sent to the child. This does not change the
        physical window size. It changes the size reported to TTY-aware
        applications like vi or curses -- applications that respond to the
        SIGWINCH signal. '''

        # Check for buggy platforms. Some Python versions on some platforms
        # (notably OSF1 Alpha and RedHat 7.1) truncate the value for
        # termios.TIOCSWINSZ. It is not clear why this happens.
        # These platforms don't seem to handle the signed int very well;
        # yet other platforms like OpenBSD have a large negative value for
        # TIOCSWINSZ and they don't have a truncate problem.
        # Newer versions of Linux have totally different values for TIOCSWINSZ.
        # Note that this fix is a hack.
        TIOCSWINSZ = getattr(termios, 'TIOCSWINSZ', -2146929561)
        if TIOCSWINSZ == 2148037735:
            # Same bits, but with sign.
            TIOCSWINSZ = -2146929561
        # Note, assume ws_xpixel and ws_ypixel are zero.
        s = struct.pack('HHHH', rows, cols, 0, 0)
        fcntl.ioctl(fd, TIOCSWINSZ, s)

    def _getwinsize(self, fd):

        '''This returns the terminal window size of the child tty. The return
        value is a tuple of (rows, cols). '''

        TIOCGWINSZ = getattr(termios, 'TIOCGWINSZ', 1074295912)
        s = struct.pack('HHHH', 0, 0, 0, 0)
        x = fcntl.ioctl(fd, TIOCGWINSZ, s)
        return struct.unpack('HHHH', x)[0:2]

    def _ttyraw(self, fd, when = tty.TCSAFLUSH, echo = False, raw_in = True, raw_out = False):
        mode = tty.tcgetattr(fd)[:]
        if raw_in:
            mode[tty.IFLAG] = mode[tty.IFLAG] & ~(tty.BRKINT | tty.ICRNL | tty.INPCK | tty.ISTRIP | tty.IXON)
            mode[tty.CFLAG] = mode[tty.CFLAG] & ~(tty.CSIZE | tty.PARENB)
            mode[tty.CFLAG] = mode[tty.CFLAG] | tty.CS8
            if echo:
                mode[tty.LFLAG] = mode[tty.LFLAG] & ~(tty.ICANON | tty.IEXTEN | tty.ISIG)
            else:
                mode[tty.LFLAG] = mode[tty.LFLAG] & ~(tty.ECHO | tty.ICANON | tty.IEXTEN | tty.ISIG)
        if raw_out:
            mode[tty.OFLAG] = mode[tty.OFLAG] & ~(tty.OPOST)
        mode[tty.CC][tty.VMIN] = 1
        mode[tty.CC][tty.VTIME] = 0
        tty.tcsetattr(fd, when, mode)

# -------------------------------------------------
# =====> command line usage as a standalone app <=====

def usage():
    print("""
usage:

    $ zio [options] cmdline | host port

options:

    -h, --help              help page, you are reading this now!
    -i, --stdin             tty|pipe, specify tty or pipe stdin, default to tty
    -o, --stdout            tty|pipe, specify tty or pipe stdout, default to tty
    -t, --timeout           integer seconds, specify timeout
    -r, --read              how to print out content read from child process, may be RAW(True), NONE(False), REPR, HEX
    -w, --write             how to print out content written to child process, may be RAW(True), NONE(False), REPR, HEX
    -a, --ahead             message to feed into stdin before interact
    -b, --before            don't do anything before reading those input
    -d, --decode            when in interact mode, this option can be used to specify decode function REPR/HEX to input raw hex bytes
    -l, --delay             write delay, time to wait before write

examples:

    $ zio -h
        you are reading this help message

    $ zio [-t seconds] [-i [tty|pipe]] [-o [tty|pipe]] "cmdline -x opts and args"
        spawning process and interact with it

    $ zio [-t seconds] host port
        zio becomes a netcat

    $ zio tty
    $ zio cat
    $ zio vim
    $ zio ssh -p 22 root@127.0.0.1
    $ zio xxd
    $ zio 127.1 22                 # WOW! you can talk with sshd by hand!
    $ zio -i pipe ssh root@127.1   # you must be crazy to do this!
""")

def cmdline(argv):
    import getopt       # use getopt for better compatibility, argparse is not introduced until python2.7
    try:
        opts, args = getopt.getopt(argv, 'hi:o:t:r:w:d:a:b:l:', ['help', 'stdin=', 'stdout=', 'timeout=', 'read=', 'write=', 'decode=', 'ahead=', 'before=', 'debug=', 'delay='])
    except getopt.GetoptError as err:
        print(str(err))
        usage()
        sys.exit(10)

    kwargs = {
        'stdin': TTY,                     # don't use tty_raw now let's say few people use raw tty in the terminal by hand
        'stdout': TTY,
    }
    decode = None
    ahead = None
    before = None
    for o, a in opts:
        if o in ('-h', '--help'):
            usage()
            sys.exit(0)
        elif o in ('-i', '--stdin'):
            if a.lower() == TTY.lower():
                kwargs['stdin'] = TTY
            elif a.lower() == TTY_RAW.lower():
                kwargs['stdin'] = TTY_RAW
            else:
                kwargs['stdin'] = PIPE
        elif o in ('-o', '--stdout'):
            if a.lower() == PIPE.lower():
                kwargs['stdout'] = PIPE
            elif a.lower() == TTY_RAW.lower():
                kwargs['stdout'] = TTY_RAW
            else:
                kwargs['stdout'] = TTY
        elif o in ('-t', '--timeout'):
            try:
                kwargs['timeout'] = int(a)
            except:
                usage()
                sys.exit(11)
        elif o in ('-r', '--read'):
            if a.lower() == 'hex':
                kwargs['print_read'] = COLORED(HEX, 'yellow')
            elif a.lower() == 'repr':
                kwargs['print_read'] = COLORED(REPR, 'yellow')
            elif a.lower() == 'none':
                kwargs['print_read'] = NONE
            else:
                kwargs['print_read'] = RAW
        elif o in ('-w', '--write'):
            if a.lower() == 'hex':
                kwargs['print_write'] = COLORED(HEX, 'cyan')
            elif a.lower() == 'repr':
                kwargs['print_write'] = COLORED(REPR, 'cyan')
            elif a.lower() == 'none':
                kwargs['print_write'] = NONE
            else:
                kwargs['print_write'] = RAW
        elif o in ('-d', '--decode'):
            if a.lower() == 'eval':
                decode = EVAL
            elif a.lower() == 'unhex':
                decode = UNHEX
        elif o in ('-a', '--ahead'):
            ahead = a
        elif o in ('-b', '--before'):
            before = a
        elif o in ('--debug',):
            kwargs['debug'] = open(a, 'w')
        elif o in ('-l', '--delay'):
            kwargs['write_delay'] = float(a)

    target = None
    if len(args) == 2:
        try:
            port = int(args[1])
            if is_hostport_tuple((args[0], port)):
                target = (args[0], port)
        except:
            pass
    if not target:
        if len(args) == 1:
            target = args[0]
        else:
            target = args

    io = zio(target, **kwargs)
    if before:
        io.read_until(before)
    if ahead:
        io.write(ahead)
    io.interact(read_transform=decode)

def main():
    if len(sys.argv) < 2:
        usage()
        sys.exit(0)

    cmdline(sys.argv[1:])

if __name__ == '__main__':
    main()

# -------------------------------------------------
# =====> export useful objects and functions <=====

__all__ = [
    'l8', 'b8', 'l16', 'b16', 'l32', 'b32', 'l64', 'b64', 'convert_packing',
    'colored',
    'match_pattern',
    'xor', 'bytes2hex', 'hex2bytes', 'tohex', 'unhex',
    'zio',
    'HEX', 'TOHEX', 'UNHEX', 'EVAL', 'REPR', 'RAW', 'NONE',
    'COLORED',
    'TTY', 'PIPE', 'TTY_RAW',
]

# vi:set et ts=4 sw=4 ft=python :
