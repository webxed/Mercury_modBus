#!/usr/bin/python3
#-*- coding: utf-8 -*-

# Mercury_remote, allows you to remotely receive data from an electricity meter
# Copyright (C) 2018 Novokreshchenov Oleg xmanchan@gmail.com
#
# Copyright (C) Pavel Markovskiy (mail@mpavel.ru) 2023 for Zabbix export
# https://habr.com/ru/companies/zabbix/articles/337856/
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see http://www.gnu.org/licenses/
 
# Скрипт для удаленного снятия показаний со счетчика Меркурий
# https://www.incotexcom.ru/files/em/docs/merkuriy-sistema-komand-ver-1-ot-2023-05-15.pdf

import serial
import struct
import time
import json
from pyzabbix import ZabbixMetric, ZabbixSender


DEBUG_PRINT = False


def myprint( var ) :
    if DEBUG_PRINT :
      print( var )

class COMport :
    def __init__(self, COMport:str) -> None:
        self.COMport = COMport
        # Open COM port
        self.Open()

    def modbusCrc(self, msg:str) -> int:
        crc = 0xFFFF
        for n in range(len(msg)):
            crc ^= msg[n]
            for i in range(8):
                if crc & 1:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return crc


    def Open(self):
        # Open serial port
        self.port = serial.Serial(self.COMport, 9600, serial.EIGHTBITS, serial.PARITY_NONE, serial.STOPBITS_ONE)
        myprint ( "Connected: %s\n\r" % self.port.isOpen() )

    def Close(self):
        # Close connection
        self.port.close()
        myprint ( 'Disconnected' )

    def Login(self, SN:int):
        self.SN = hex(SN).replace('0x', '')
        # Open Power Metre connection
        self.sendReceive('00')
        # Eneter password - Level 1
        self.sendReceive('0101010101010101')
    
    def Logout(self):
        self.sendReceive('02')


    def sendReceive(self, chunk, info = ''):

        chunk = bytes.fromhex(self.SN + chunk)

        chunk += self.modbusCrc(chunk).to_bytes(2, byteorder='little')

        if( len(info) ):
            myprint(info)

        myprint ('Request string: %s' % ' '.join('{:02x}'.format(c) for c in chunk) )

        # Send data
        self.port.write(chunk)
        time.sleep(1)
        out = self.port.read_all()

        myprint ('Result string: %s' % ' '.join('{:02x}'.format(c) for c in out))
        myprint ("\n\r")

        return out



class MercuryData:
    def __init__(self, Host ) :
        self.ret = { 'Ph' : [], 'Temp' : [], 'U' : [], 'P' : [] }
        self.Host = Host
        self.ZBXpacket = []

    # Текущие показания сумма 4.3.1 Энергия за 12 месяцев
    # 05 00 00
    # exmp. 83 00 00 0F 08 FF FF FF FF 00 00 DA 00 00 00 C5 03 E5 41
    def getPh( self, out ):
        P = out[1:3][::-1] + out[3:5][::-1]
        self.ZBXpacket.append( ZabbixMetric(self.Host, 'Ph', self.ret['Ph']) )
    
    # Текущая температура
    # 08 11 70
    # exmp. 83 00 0C 80 2D
    def getTemp(self, out):
        self.ret['Temp'] = int.from_bytes(out[2:3], byteorder='big') 
        self.ZBXpacket.append( ZabbixMetric(self.Host, 'Temp', self.ret['Temp']) )

    # 4.4.15 Мгновенные значения
    # 4.4.15.2.1 Мощность merkuriy-sistema-komand-ver-1-ot-2023-05-15.pdf
    # 83 08 16 00 A6 02
    # \x83[\x40\x5A\x01][\x40\xDC\x00][\x40\x7E\x00][\x00\x00\x00]\x93\xCA 
    def getP(self, out):
        self.ret['P'] = {
                            'ps'  : int.from_bytes(out[2:4][::-1],   byteorder='big')/100,
                            'p1'  : int.from_bytes(out[5:7][::-1],   byteorder='big')/100,
                            'p2'  : int.from_bytes(out[8:10][::-1],  byteorder='big')/100,
                            'p3'  : int.from_bytes(out[10:12][::-1], byteorder='big')/100,
                        }

        self.ZBXpacket.append( ZabbixMetric(self.Host, 'P[ps]', self.ret['P']['ps']) )
        self.ZBXpacket.append( ZabbixMetric(self.Host, 'P[p1]', self.ret['P']['p1']) )
        self.ZBXpacket.append( ZabbixMetric(self.Host, 'P[p2]', self.ret['P']['p2']) )
        self.ZBXpacket.append( ZabbixMetric(self.Host, 'P[p3]', self.ret['P']['p3']) )

    # 4.4.15 Мгновенные значения
    # Напряжение по фазам
    # 08 16 11
    # Result string: 8e:00:[72:5c]:00:[ae:5c]:00:[f1:5c]:b2:c3
    def getU(self, out):
        self.ret['U'] = {  
                            'p1' : int.from_bytes(out[2:4][::-1],  byteorder='big')/100,
                            'p2' : int.from_bytes(out[5:7][::-1],  byteorder='big')/100, 
                            'p3' : int.from_bytes(out[8:10][::-1], byteorder='big')/100,
                        }

        self.ZBXpacket.append( ZabbixMetric(self.Host, 'U[p1]', self.ret['U']['p1']) )
        self.ZBXpacket.append( ZabbixMetric(self.Host, 'U[p2]', self.ret['U']['p2']) )
        self.ZBXpacket.append( ZabbixMetric(self.Host, 'U[p3]', self.ret['U']['p3']) )
     
     def getA(self, out):
        self.ret['A'] = {
                            'A1' : int.from_bytes(out[2:4][::-1],  byteorder='big')/1000, # ''.join( '{:02x}'.format(c) for c in out[2:4] ),
                            'A2' : int.from_bytes(out[5:7][::-1],  byteorder='big')/1000,
                            'A3' : int.from_bytes(out[8:10][::-1], byteorder='big')/1000,
                        }     
        self.ZBXpacket.append( ZabbixMetric(self.Host, 'A[a1]', self.ret['A']['a1']) )
        self.ZBXpacket.append( ZabbixMetric(self.Host, 'A[a2]', self.ret['A']['a2']) )
        self.ZBXpacket.append( ZabbixMetric(self.Host, 'A[a3]', self.ret['A']['a3']) )


com = '/dev/ttyr01'

Devices = [
111, 112, 121, 122, 131, 132, 141, 142, 151, 152, 161, 162, 171, 172, 181, 182, 191, 192
]

#Devices = [112]
DevicesData = {}

Modem = COMport( com )

for device in Devices :

    # Modem.sendReceive('0803', '# 4.4.5 Версия ПО счетчика')

    Modem.Login( device )

    Host = "Mercury" + str(device)

    Mercury = MercuryData( Host )

    Mercury.getTemp( Modem.sendReceive('081170', '# температура внутри прибора' ) )
    Mercury.getPh(   Modem.sendReceive('050000', '# Текущие показания сумма 4.3.1 Энергия за 12 месяцев') )
    Mercury.getP(    Modem.sendReceive('081600', '# мощность') )
    Mercury.getU(    Modem.sendReceive('081611', '# фазное напряжение') )

    # DevicesData.append( {Host : Mercury.ret} )
    DevicesData[Host] = Mercury.ret

    if len(Mercury.ZBXpacket) :
        print(Mercury.ZBXpacket)
        result = ZabbixSender(use_config=True).send(Mercury.ZBXpacket)
        print( result )

    #print( json.dumps(DevicesData) )

    Modem.Logout()



print( json.dumps(DevicesData) )

Modem.Close()
