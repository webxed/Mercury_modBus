#!/usr/bin/python3
#-*- coding: utf-8 -*-

# Mercury_remote, allows you to remotely receive data from an electricity meter
# Copyright (C) 2018 Novokreshchenov Oleg xmanchan@gmail.com
# https://habr.com/ru/articles/418209/
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
from datetime import datetime

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


        #print(out)
        #print('==========')
        #print(out[-2:])
        #print('==========')
        #print(print(out[:-2]) ) # self.modbusCrc(out[:-2])

        myprint ('Result string: %s' % ' '.join('{:02x}'.format(c) for c in out))
        #myprint ('Check CRC: %s' % out[-2:] == self.modbusCrc(out[:-2]))
        myprint ("\n\r")

        return out



class MercuryData:
    def __init__(self, sn) :
        self.ret = { 'SN' : sn }

    # Текущие показания сумма 4.3.1 Энергия за 12 месяцев
    # 05 00 00
    # exmp. 83 00 00 0F 08 FF FF FF FF 00 00 DA 00 00 00 C5 03 E5 41
    def getPh( self, out ):
        #P = out[1:5].lstrip(b'\x83\x00')[::-1];
        P = out[1:2][::-1] + out[3:5][::-1];
        self.ret['EA'] = ( int.from_bytes(P, byteorder='big') / 1000 )

    # Текущая температура
    # 08 11 70
    # exmp. 83 00 0C 80 2D
    def getTemp(self, out):
        self.ret['Temp'] = int.from_bytes(out[2:3], byteorder='big')

    # 4.4.15 Мгновенные значения
    # 4.4.15.2.1 Мощность merkuriy-sistema-komand-ver-1-ot-2023-05-15.pdf
    # 83 08 16 00 A6 02
    # \x83[\x40\x5A\x01][\x40\xDC\x00][\x40\x7E\x00][\x00\x00\x00]\x93\xCA 
    def getP(self, out):
        self.ret['Psum'] = int.from_bytes(out[2:4][::-1],   byteorder='big')/100 
        self.ret['P1'] = int.from_bytes(out[5:7][::-1],   byteorder='big')/100
        self.ret['P2'] = int.from_bytes(out[8:10][::-1],  byteorder='big')/100 
        self.ret['P3'] = int.from_bytes(out[10:12][::-1], byteorder='big')/100


    # 4.4.15 Мгновенные значения
    # Напряжение по фазам
    # 08 16 11
    # Result string: 8e:00:[72:5c]:00:[ae:5c]:00:[f1:5c]:b2:c3
    def getU(self, out):
        self.ret['U1'] =  int.from_bytes(out[2:4][::-1],  byteorder='big')/100
        self.ret['U2'] =  int.from_bytes(out[5:7][::-1],  byteorder='big')/100
        self.ret['U3'] =  int.from_bytes(out[8:10][::-1], byteorder='big')/100


com = '/dev/ttyr03'

Devices = [111, 112, 121, 122, 131, 132, 141, 142, 151, 152, 161, 162, 171, 172, 181, 182, 191, 192]
DevicesData = []

Modem = COMport( com )

sDate = datetime.today().strftime('%Y-%m-%d')
sTime = datetime.today().strftime('%H:%M')

print('\n')

for device in Devices :
    # Modem.sendReceive('0803', '# 4.4.5 Версия ПО счетчика')

    Modem.Login( device )

    Mercury = MercuryData( device )

    Mercury.getTemp( Modem.sendReceive('081170', '# температура внутри прибора' ) )
    Mercury.getPh(   Modem.sendReceive('050000', '# Текущие показания сумма 4.3.1 Энергия за 12 месяцев') )
    #Mercury.getP(    Modem.sendReceive('081600', '# мощность') )
    Mercury.getU(    Modem.sendReceive('081611', '# фазное напряжение') )

    #Host = "Mercury" + str(device)

    # DevicesData.append( {Host : Mercury.ret} )

    Mercury.ret['Date'] = sDate
    Mercury.ret['Time'] = sTime
    DevicesData.append(Mercury.ret)

    #print( json.dumps(DevicesData) )

    Modem.Logout()

print( json.dumps(DevicesData) )

Modem.Close()

