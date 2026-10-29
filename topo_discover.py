# -*- coding: utf-8 -*-
"""
topo_discover.py - Trabalho SDN Parte 1
Controlador Ryu (OpenFlow 1.3) que descobre switches, enlaces e hosts.

Executar com:  ryu-manager --observe-links topo_discover.py
  --observe-links : faz o modulo ryu.topology enviar LLDP por todas as portas
                    dos switches e assim descobrir os enlaces.
"""
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.topology import event
from ryu.topology.api import get_switch, get_link
from ryu.lib.packet import packet, arp


class TopoDiscover(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(TopoDiscover, self).__init__(*args, **kwargs)
        self.topology_api_app = self
        self.switches = []      # [dpid, ...]
        self.links = []         # [(src_dpid, dst_dpid, src_port, dst_port), ...]
        self.hosts = {}         # {ip: {'mac': mac, 'dpid': dpid, 'port': port}}

    # ------------------------------------------------------------------
    # Table-miss: sem esta regra o switch OpenFlow 1.3 DESCARTA pacotes sem
    # regra e nenhum Packet-In (ARP) chegaria ao controlador.
    # ------------------------------------------------------------------
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def _switch_features_handler(self, ev):
        dp = ev.msg.datapath
        ofp, parser = dp.ofproto, dp.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER,
                                          ofp.OFPCML_NO_BUFFER)]
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        dp.send_msg(parser.OFPFlowMod(datapath=dp, priority=0,
                                      match=match, instructions=inst))

    # ------------------------------------------------------------------
    # Descoberta de switches e enlaces (API de topologia)
    # ------------------------------------------------------------------
    def _refresh_switches(self):
        switch_list = get_switch(self.topology_api_app, None)
        self.switches = sorted(sw.dp.id for sw in switch_list)

    def _refresh_links(self):
        link_list = get_link(self.topology_api_app, None)
        self.links = [(l.src.dpid, l.dst.dpid, l.src.port_no, l.dst.port_no)
                      for l in link_list]

    @set_ev_cls(event.EventSwitchEnter)
    def _event_switch_enter_handler(self, ev):
        self._refresh_switches()
        self.logger.info("Switches mapeados atualmente: %s", self.switches)

    @set_ev_cls(event.EventSwitchLeave)
    def _event_switch_leave_handler(self, ev):
        self._refresh_switches()
        self.logger.info("Switch removido. Switches atuais: %s", self.switches)

    @set_ev_cls(event.EventLinkAdd)
    def _event_link_add_handler(self, ev):
        self._refresh_links()
        self.logger.info("Total de enlaces descobertos: %d (direcionais)",
                         len(self.links))

    @set_ev_cls(event.EventLinkDelete)
    def _event_link_delete_handler(self, ev):
        self._refresh_links()
        self.logger.info("Enlace removido. Total de enlaces: %d", len(self.links))

    # ------------------------------------------------------------------
    # Descoberta de hosts via Gratuitous ARP (Packet-In)
    # ------------------------------------------------------------------
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        arp_pkt = pkt.get_protocol(arp.arp)

        if not arp_pkt:       # LLDP, IPv6 etc.: nao e do nosso interesse
            return

        self.logger.info("ARP recebido do IP %s, MAC %s no Switch %s, porta %s",
                         arp_pkt.src_ip, arp_pkt.src_mac, datapath.id, in_port)

        # Ignora ARP vindo de porta de enlace entre switches (nao e porta de host)
        if self._is_switch_port(datapath.id, in_port):
            self.logger.info("Porta %s do switch %s e enlace inter-switch; ignorado",
                             in_port, datapath.id)
            return

        # Registra/atualiza o host
        self.hosts[arp_pkt.src_ip] = {'mac': arp_pkt.src_mac,
                                      'dpid': datapath.id,
                                      'port': in_port}
        self.print_full_topology()

    def _is_switch_port(self, dpid, port):
        return any((l[0] == dpid and l[2] == port) or
                   (l[1] == dpid and l[3] == port) for l in self.links)

    # ------------------------------------------------------------------
    # Impressao da topologia completa
    # ------------------------------------------------------------------
    def print_full_topology(self):
        # Reconsulta a API para garantir dados atualizados
        self._refresh_switches()
        self._refresh_links()

        # Os enlaces sao reportados nos dois sentidos: deduplica para imprimir
        undirected = {}
        for s, d, sp, dp_ in self.links:
            key = tuple(sorted(((s, sp), (d, dp_))))
            undirected[key] = True

        log = self.logger.info
        log("=" * 62)
        log("TOPOLOGIA COMPLETA MAPEADA")
        log("=" * 62)
        log("Switches ativos (%d): %s", len(self.switches),
            ", ".join("s%d" % s for s in self.switches))
        log("-" * 62)
        log("Enlaces entre switches (%d):", len(undirected))
        for (a, ap), (b, bp) in sorted(undirected):
            log("  s%d (porta %d) <--> s%d (porta %d)", a, ap, b, bp)
        log("-" * 62)
        log("Hosts conectados (%d):", len(self.hosts))
        for ip, h in sorted(self.hosts.items(),
                            key=lambda kv: (kv[1]['dpid'], kv[1]['port'])):
            log("  host %-10s MAC %s  -> s%d (porta %d)",
                ip, h['mac'], h['dpid'], h['port'])
        log("=" * 62)
