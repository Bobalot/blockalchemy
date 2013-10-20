#!env python

import zmq
import random
from serialize import ser_data, ser_destination, ser_uint32, deser_uint32, deser_data, checksum
from binascii import hexlify, unhexlify
from error_code import *

from time import sleep, time

import threading
import Queue
#from bctypes import *
import atexit

context = zmq.Context(1)

def msleep(length):
    sleep(length/1e3)

class ObeliskRequest(object):
    def __init__(self):
        self.destination = None
        self.command = ''
        self.id = random.randint(0, 2**32)
        data = None


class ObeliskResponse(object):
    def __init__(self):
        self.origin = None
        self.command = str()
        self.id = int()
        self.data = None
        self.response_checksum = None
        self.error_code = 0


#class ObeliskService(object):
#    def __init__(self, address='localhost', port=9091):
#        self.context = zmq.Context(1)
#        #self.socket = context.socket(zmq.DEALER)
#        #self.socket.setsockopt(zmq.LINGER, 0)
#        self.address = address
#        self.port = port
#
#        self.stopped = False
#
#        # Requests is mapping of id : ObeliskRequest.
#        # Useful to re-lookup the request in case we have to send it again
#        # due to network issues, or bad checksum.
#        self._requests = {}
#
#        # Response holds all the ObeliskResponse objects, after they have been returned.
#        # They can be popped from the dict once they have been read.
#        self._responses = {}
#
#        # Subscriptions is a map of id: callback_function.
#        self._subscriptions = {}
#
#        t = threading.Thread(target = self.poller)
#        t.start()
#
#
#    def __del__(self):
#        self.context.term()
#
#    def poller(self):
#        while not self.stopped:
#
#
#    def send_request(self, req):
#        # serialize the data.
#        data = ser_data(req.command, req.data)
#
#        #print hexlify(data)
#
#        socket = context.socket(zmq.DEALER)
#        socket.connect("tcp://" + self.address + ":" + str(self.port))
#        socket.setsockopt(zmq.LINGER, 0)
#
#        socket.send(ser_destination(req.destination), zmq.SNDMORE)
#        socket.send(req.command, zmq.SNDMORE)
#        socket.send(ser_uint32(req.id), zmq.SNDMORE)
#        socket.send(data, zmq.SNDMORE)
#        socket.send(checksum(data))
#
#        poller = zmq.Poller()
#        poller.register(socket, zmq.POLLIN)
#
#        resp_frame = []
#
#        while True:
#
#            socks = dict(poller.poll(1000))
#            if socks:
#                if socks.get(socket) == zmq.POLLIN:
#                    message = socket.recv(zmq.NOBLOCK)
#                    #print "got message ", hexlify(message)
#                    resp_frame.append(message)
#                if len(resp_frame) == 5:
#                    break
#            else:
#                #print "error: message timeout"
#                break
#
#        response = ObeliskResponse()
#        response.origin = resp_frame[0]
#        response.command = resp_frame[1]
#        response.id = deser_uint32(resp_frame[2])
#        response.error_code = resp_frame[3][0:4]
#        response.data = deser_data(response.command, resp_frame[3][4:])
#        response.checksum = resp_frame[4]
#
#        socket.close()
#
#        return response
#
#    def send_blocking(self):
#        pass
#
#
#    def subscribe(self, ):
#        pass
#
#    def send_command(self, command, data):
#        pass




class ObeliskService(object):
    def __init__(self, address='localhost', port=9091):
        self.context = zmq.Context(1)
        #self.socket = context.socket(zmq.DEALER)
        #self.socket.setsockopt(zmq.LINGER, 0)
        self.address = address
        self.port = port

        self.stopped = False

        self.socket = context.socket(zmq.DEALER)
        self.socket.connect("tcp://" + self.address + ":" + str(self.port))
        self.socket.setsockopt(zmq.LINGER, 0)


        # requests to send go into here. Once they are sent they're removed and added to self._requests
        self._outgoing_queue = Queue.Queue()

        # Requests is mapping of id : ObeliskRequest.
        # Useful to re-lookup the request in case we have to send it again
        # due to network issues, or bad checksum.
        # once we have a successful response, the request is removed from here and a response is added to _response
        # with the same id key
        self._requests = {}

        # Response holds all the ObeliskResponse objects, after they have been returned.
        # They can be popped from the dict once they have been read.
        self._responses = {}

        # callbacks is a map of id: callback_function.
        self._callbacks = {}

        self.poller_thread = threading.Thread(target=self.poller)
        self.poller_thread.daemon = True
        self.poller_thread.start()

        self.sender_thread = threading.Thread(target=self.sender)
        self.sender_thread.daemon = True
        self.sender_thread.start()

        atexit.register(self.stop)

    def __del__(self):
        self.stop()

        self.socket.close()
        self.context.term()

    def stop(self):
        self.stopped = True
        self.poller_thread.join()
        self.sender_thread.join()

    def poller(self):

        poller = zmq.Poller()
        poller.register(self.socket, zmq.POLLIN)

        while not self.stopped:
            socks = dict(poller.poll(1000))
            if socks:
                if socks.get(self.socket) == zmq.POLLIN:
                    #message = self.socket.recv(zmq.NOBLOCK)
                    #resp_frame.append(message)

                    resp_frame = self.socket.recv_multipart(zmq.NOBLOCK)

                    #print resp_frame

                    if len(resp_frame) == 5:

                        response = ObeliskResponse()
                        response.origin = resp_frame[0]
                        response.command = resp_frame[1]
                        response.id = deser_uint32(resp_frame[2])

                        response.error_code, response.data = deser_data(response.command, resp_frame[3])
                        response.checksum = resp_frame[4]

                        #print "got command, ", response.command
                        #print "got data, ", response.data

                        # validate data if it fails, try and send the request again and del this response
                        # if the request is no longer in _requests ignore it.
                        if checksum(resp_frame[3]) != response.checksum:
                            try:
                                self.send_request(self._requests[response.id])
                                del response
                            except KeyError:
                                pass

                        # Message is fine, remove the request from _requests and add our response to _response
                        else:

                            # If there isn't a callback related to this id, pop it from the requests and insert
                            # the result into responses.
                            if response.id not in self._callbacks:
                                self._requests.pop(response.id)
                                self._responses[response.id] = response

                            else:
                                print "callbacked"
                                # Try and pop the old request out of the request dict.
                                # It doesn't need to exist any more as the server has received the message
                                try:
                                    self._requests.pop(response.id)
                                except KeyError:
                                    pass

                                # Call the callback function in _callbacks
                                try:
                                    if response.data is not None:
                                        self._callbacks[response.id](response.data)
                                except KeyError:
                                    pass


    def sender(self):
        while not self.stopped:
            try:
                req = self._outgoing_queue.get(True, 1)

                data = ser_data(req.command, req.data)
                self._requests[req.id] = req

                self.socket.send(ser_destination(req.destination), zmq.SNDMORE)
                self.socket.send(req.command, zmq.SNDMORE)
                self.socket.send(ser_uint32(req.id), zmq.SNDMORE)
                self.socket.send(data, zmq.SNDMORE)
                self.socket.send(checksum(data))

                self._outgoing_queue.task_done()
            except Queue.Empty:
                #print "queue empty"
                #msleep(500)
                pass


    def response(self, msg_id):
        return self._responses.pop(msg_id)


    def block(self, msg_id, timeout=30):
        start_time = time()
        while time() < start_time + timeout:
            try:
                return self.response(msg_id)
            except KeyError:
                msleep(50)


    #def send_request(self, req):
    #    # serialize the data.
    #    data = ser_data(req.command, req.data)
    #
    #    #print hexlify(data)
    #    #socket = context.socket(zmq.DEALER)
    #    #socket.connect("tcp://" + self.address + ":" + str(self.port))
    #    #socket.setsockopt(zmq.LINGER, 0)
    #
    #    self.socket.send(ser_destination(req.destination), zmq.SNDMORE)
    #    self.socket.send(req.command, zmq.SNDMORE)
    #    self.socket.send(ser_uint32(req.id), zmq.SNDMORE)
    #    self.socket.send(data, zmq.SNDMORE)
    #    self.socket.send(checksum(data))
    #
    #    poller = zmq.Poller()
    #    poller.register(socket, zmq.POLLIN)
    #
    #    resp_frame = []
    #
    #    while True:
    #
    #        socks = dict(poller.poll(1000))
    #        if socks:
    #            if socks.get(socket) == zmq.POLLIN:
    #                message = socket.recv(zmq.NOBLOCK)
    #                #print "got message ", hexlify(message)
    #                resp_frame.append(message)
    #            if len(resp_frame) == 5:
    #                break
    #        else:
    #            #print "error: message timeout"
    #            break
    #
    #    response = ObeliskResponse()
    #    response.origin = resp_frame[0]
    #    response.command = resp_frame[1]
    #    response.id = deser_uint32(resp_frame[2])
    #    response.error_code = resp_frame[3][0:4]
    #    response.data = deser_data(response.command, resp_frame[3][4:])
    #    response.checksum = resp_frame[4]
    #
    #    socket.close()
    #
    #    return response

    # Returns immediately after adding the request to the queue
    def send_request(self, req):
        self._outgoing_queue.put(req, block=True)


    def subscribe(self, req, callback):
        self._callbacks[req.id] = callback
        self.send_request(req)

    # blocks and returns the resp object if it is available within 30 seconds,
    # otherwise it may be available through response(req.id) at a later time.
    def send_blocking(self, req, timeout=30):
        id = req.id
        self.send_request(req)

        resp = self.block(id, timeout=timeout)
        return resp

    #Blocks and handles the error code for us
    def send_command(self, command, data):
        req = ObeliskRequest()
        req.command = command
        req.data = data

        result = self.send_blocking(req)

        return result.data

    # Builds and sends a subscription.
    def send_subscription(self, command, data, callback):
        req = ObeliskRequest()
        req.command = command
        req.data = data

        self.subscribe(req, callback)


service = ObeliskService("localhost", 9091)


# Wrapper class
class ObeliskBase(object):
    def __init__(self):
        pass

Base = ObeliskBase
Base.service = service

