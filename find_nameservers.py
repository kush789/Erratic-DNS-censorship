import sys

import ipaddress
import functools
import janus

import asyncio
import dns.asyncquery
import dns.asyncresolver


async def nameserver_probe(potential_nameservers, identified_nameservers, 
                           probe_hostname, timeout_in_seconds, max_probe_count):
    while True:
        if potential_nameservers.async_q.empty():
            return

        potential_nameserver, retry_count = \
            await potential_nameservers.async_q.get()

        if retry_count == max_probe_count:
            continue

        print ("Checking %s retry %d" % (potential_nameserver, retry_count))

        try:
            query = dns.message.make_query(probe_hostname, 'A')
            response = await dns.asyncquery.udp(query, 
                potential_nameserver, timeout = timeout_in_seconds)

            await identified_nameservers.async_q.put(potential_nameserver)
            print ("\n\n=====> Found nameserver", 
                potential_nameserver, response, "\n\n")

        except:
            await potential_nameservers.async_q.put(
                (potential_nameserver, retry_count + 1))


async def probe_network_ranges(network_ranges, probe_hostname, 
                               timeout_in_seconds, max_probe_count):
    
    potential_nameserver_generators = map(
        lambda network_range: ipaddress.ip_network(network_range).hosts(),
        network_ranges)

    potential_nameservers = janus.Queue()
    for potential_nameserver_generator in potential_nameserver_generators:
        for potential_nameserver in potential_nameserver_generator:
            potential_nameservers.sync_q.put((str(potential_nameserver), 0))

    identified_nameservers = janus.Queue()

    nameserver_checkers = [
        nameserver_probe(potential_nameservers, identified_nameservers,
            probe_hostname, timeout_in_seconds, max_probe_count) 
        for _ in range(512)]
    await asyncio.gather(*nameserver_checkers)

    with open("nameservers.txt", "w") as fp:
        while not identified_nameservers.sync_q.empty():
            ns = identified_nameservers.sync_q.get()
            print ("Found Nameserver: %s\n" % (ns))
            fp.write(ns + "\n")

# Uncomment to avoid terminal clutter from timeout exceptions
class DevNull:
   def write(self, msg):
       pass
sys.stderr = DevNull()

if __name__ == "__main__":

    network_ranges = ["59.144.0.0/20"] # Network ranges to probe for resolvers
    probe_hostname = "google.com" # Dummy hostname to run DNS queries
    timeout_in_seconds = 2 # Timeout per request
    max_probe_count = 1 # Number of probe attempts per IP address

    asyncio.run(probe_network_ranges(network_ranges, probe_hostname, 
        timeout_in_seconds, max_probe_count))
