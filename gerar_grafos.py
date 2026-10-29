#!/usr/bin/env python3
"""Gera com NetworkX os grafos das topologias (switches + hosts) em PNG."""
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

# posicoes fixas imitando os diagramas do enunciado (switches)
POS = {
    "topo_triangle.txt": {1: (0, 0), 2: (1, 1.2), 3: (2, 0)},
    "topo_someloops.txt": {5: (0, 1), 1: (1.2, 1), 2: (2.4, 1),
                           3: (0, 0), 4: (1.2, 0), 6: (3.4, 0.5)},
}

def load(path):
    G = nx.Graph()
    for line in open(path):
        line = line.split('#')[0].split()
        if len(line) == 2:
            G.add_edge(line[0], line[1])
    return G

def draw(path, out):
    G = load(path)
    sw = {int(n[1:]): n for n in G.nodes}
    pos = {}
    for i, n in sw.items():
        x, y = POS[path][i]
        pos[n] = (x, y)
        pos["h%d" % i] = (x, y + (0.55 if y >= 0.5 else -0.55))   # host ao lado do switch
    H = G.copy()
    for i in sw:
        H.add_edge("s%d" % i, "h%d" % i)
    plt.figure(figsize=(8, 5))
    nx.draw_networkx_edges(G, pos, width=2.2)
    nx.draw_networkx_edges(H, pos, edgelist=[("s%d" % i, "h%d" % i) for i in sw],
                           style="dashed", width=1.2)
    nx.draw_networkx_nodes(G, pos, node_color="#4C78A8", node_size=1100)
    nx.draw_networkx_nodes(H, pos, nodelist=["h%d" % i for i in sw],
                           node_color="#F2A541", node_shape="s", node_size=800)
    nx.draw_networkx_labels(H, pos, font_color="white", font_size=11)
    plt.title("%s  (%d switches, %d enlaces)" % (path, G.number_of_nodes(),
                                                  G.number_of_edges()))
    plt.axis("off"); plt.margins(0.15); plt.tight_layout()
    plt.savefig(out, dpi=150); plt.close()

if __name__ == "__main__":
    draw("topo_triangle.txt", "figuras/grafo_triangle.png")
    draw("topo_someloops.txt", "figuras/grafo_someloops.png")
    print("Grafos gerados em figuras/")
