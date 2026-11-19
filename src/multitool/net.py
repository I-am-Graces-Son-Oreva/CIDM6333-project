import ipaddress


def network_info(cidr: str) -> dict[str, str | int]:
    network = ipaddress.ip_network(cidr)
    is_ipv4 = isinstance(network, ipaddress.IPv4Network)

    if is_ipv4 and network.prefixlen < 31:
        first_host = network.network_address + 1
        last_host = network.broadcast_address - 1
        host_count = network.num_addresses - 2
    elif not is_ipv4 and network.prefixlen < 127:
        first_host = network.network_address + 1
        last_host = network.broadcast_address
        host_count = network.num_addresses - 1
    else:
        first_host = network.network_address
        last_host = network.broadcast_address
        host_count = network.num_addresses

    return {
        "network": str(network),
        "broadcast": str(network.broadcast_address),
        "netmask": str(network.netmask),
        "first_host": str(first_host),
        "last_host": str(last_host),
        "host_count": host_count,
    }
