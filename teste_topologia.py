#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
teste_topologia.py - Trabalho SDN Parte 1
Le um arquivo de lista de arestas (switch switch), instancia a rede no Mininet
(um host por switch), conecta ao controlador Ryu remoto (OpenFlow 1.3) e
dispara um Gratuitous ARP em cada host para que o controlador os descubra.

Uso: sudo python3 teste_topologia.py topo_triangle.txt
"""
import re
import sys
from time import sleep

from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info


def parse_edge_list(path):
    """Faz o parsing do arquivo de arestas.

    Cada linha valida tem o formato 'sA sB'. Linhas vazias e comentarios (#)
    sao ignorados. Retorna (lista_de_arestas, lista_ordenada_de_ids).
    O id numerico do switch (ex.: 's3' -> 3) e usado como DPID, nome do host
    (h3) e ultimo octeto do IP (10.0.0.3).
    """
    edges, ids = [], set()
    with open(path) as f:
        for n, line in enumerate(f, 1):
            line = line.split('#')[0].strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 2 or not all(re.fullmatch(r's\d+', p) for p in parts):
                raise ValueError("Linha %d invalida em %s: %r" % (n, path, line))
            a, b = parts
            if a == b:
                raise ValueError("Linha %d: laco (self-loop) nao permitido" % n)
            edge = tuple(sorted((a, b), key=lambda s: int(s[1:])))
            if edge in edges:      # ignora aresta duplicada
                continue
            edges.append(edge)
            ids.update((int(a[1:]), int(b[1:])))
    return edges, sorted(ids)


def start_network(edge_list_file):
    edges, ids = parse_edge_list(edge_list_file)

    net = Mininet(controller=RemoteController, switch=OVSKernelSwitch)
    net.addController('c0', port=6633)

    # 1) Switches (DPID = numero do switch, forcando OpenFlow 1.3)
    switches = {}
    for i in ids:
        switches[i] = net.addSwitch('s%d' % i, dpid='%016x' % i,
                                    protocols='OpenFlow13')

    # 2) Um host por switch. O link do host e criado ANTES dos enlaces entre
    #    switches, entao a porta 1 de cada switch sempre aponta para seu host.
    for i in ids:
        h = net.addHost('h%d' % i, ip='10.0.0.%d/24' % i,
                        mac='00:00:00:00:00:%02x' % i)
        net.addLink(h, switches[i])

    # 3) Enlaces entre switches conforme o arquivo
    for a, b in edges:
        net.addLink(switches[int(a[1:])], switches[int(b[1:])])

    info('*** Topologia: %d switches, %d hosts, %d enlaces entre switches\n'
         % (len(ids), len(ids), len(edges)))

    net.start()
    print("Aguardando inicializacao do controlador e descoberta LLDP...")
    sleep(5)   # tempo para o Ryu descobrir os enlaces antes dos ARPs

    print("Enviando Gratuitous ARP de todos os hosts para descoberta pelo Ryu...")
    for h in net.hosts:
        # -U: ARP nao solicitado (gratuitous); -I: interface do host
        h.cmd('arping -U -c 1 -I %s %s' % (h.defaultIntf().name, h.IP()))
        sleep(0.1)

    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    if len(sys.argv) > 1:
        start_network(sys.argv[1])
    else:
        print("Uso: sudo python3 teste_topologia.py <arquivo_topologia.txt>")
