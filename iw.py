import subprocess
import pcap
import dpkt
import os
import time

import client

class IW:
	def __init__(self, netif, authorized):
		if not netif:
			return
		self.netif = netif
		self.authorized = authorized
		self.detected = {}
		self.channel = 1
		self.quit = False
		self.DEVNULL = open(os.devnull, 'w')
		if subprocess.call(["airmon-ng", "start", netif], stdout=self.DEVNULL, stderr=self.DEVNULL) != 0:
			print("[netif %s] cannot set monitor mode" % (self.netif))
			self.quit = True
			return
		else:
			self.netif += "mon"

		self.set_channel(1)

	def set_channel(self, channel):
		if subprocess.call(["iw", "dev", self.netif, "set", "channel", str(channel)], stdout=self.DEVNULL, stderr=self.DEVNULL) != 0:
			print("[netif %s] cannot set channel to %d" % (self.netif, channel))
			return False
		self.channel = channel
		#print("[netif %s] set channel to %d" % (self.netif, channel))
		return True
			

	def loop(self):
		try:
			pc = pcap.pcap(self.netif)
			counter = 0
			for timestamp, packet in pc:
				if self.quit:
					break
				parsed = None
				try:
					parsed = dpkt.radiotap.Radiotap(packet).data
				except dpkt.dpkt.NeedData:
					continue
				if parsed.type == 0 and parsed.subtype == 8:
					src = ":".join("{:02x}".format(ord(c)) for c in parsed.mgmt.src)
					t = (parsed.ssid.info, src)
					ts = "%s-%s" % t
					if t not in self.authorized:
						if ts not in self.detected:
							self.detected[ts] = {
								"lastseen" : time.time(),
								"lastreported" : time.time()
							}
							print("[netif %s] Unauthorized AP detected: %s" % (self.netif, str(t)))
							self.report(t[0], src)
						else:
							te = self.detected[ts]
							te["lastseen"] = time.time()
							if te["lastseen"] - te["lastreported"] > 60:
								self.report(t[0], src)
							
		except KeyboardInterrupt as e:
			print("[netif %s] signal received, quitting" % (self.netif))
			self.quit = True
			self.close()
			return
			
	def close(self):
		if subprocess.call(["airmon-ng", "stop", self.netif], stdout=self.DEVNULL, stderr=self.DEVNULL) != 0:
			print("[netif %s] cannot deactivate monitor mode" % self.netif)

	def report(self, name, mac):
		sc = client.ServerClient()
		csuc, rsuc, verdict, msg = sc.report(name, mac)
		if not csuc:
			print("[netif %s] Cannot connect to server: %s" % (self.netif, msg))
		elif not rsuc:
			print("[netif %s] Cannot report to server: %s" % (self.netif, msg))

		if verdict:
			print("[netif %s] Administering fatal verdict to %s" % (self.netif, name))
