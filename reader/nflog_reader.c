/*
 * reader/nflog_reader.c - Zero-DPI C Netlink NFLOG Reader
 * Tata Elxsi TELIPORT S4 · Problem Statement 3
 * 
 * Complies with C2: Extracts ONLY timestamp, protocol, 5-tuple, IP total length,
 * and TCP flags. Discards any payload bytes immediately in C before IPC.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <netinet/ip.h>
#include <netinet/tcp.h>
#include <netinet/udp.h>
#include <linux/netlink.h>
#include <linux/netfilter/nfnetlink.h>
#include <linux/netfilter/nfnetlink_log.h>

#define BUFSIZE 65536

#ifndef NLA_OK
#define NLA_OK(nla,len) ((len) >= (int)sizeof(struct nlattr) && \
                         (nla)->nla_len >= sizeof(struct nlattr) && \
                         (nla)->nla_len <= (len))
#endif

#ifndef NLA_NEXT
#define NLA_NEXT(nla,attrlen) ((attrlen) -= NLA_ALIGN((nla)->nla_len), \
                               (struct nlattr*)(((char*)(nla)) + NLA_ALIGN((nla)->nla_len)))
#endif

#ifndef NLA_DATA
#define NLA_DATA(nla) ((void*)(((char*)(nla)) + NLA_HDRLEN))
#endif

#ifndef NLA_PAYLOAD
#define NLA_PAYLOAD(nla) ((int)((nla)->nla_len - NLA_HDRLEN))
#endif

static void process_packet(const unsigned char *data, int len) {
    if (len < (int)sizeof(struct iphdr)) return;

    const struct iphdr *ip = (const struct iphdr *)data;
    int ihl = ip->ihl * 4;
    if (len < ihl || ip->version != 4) return;

    struct timeval tv;
    gettimeofday(&tv, NULL);

    unsigned int proto = ip->protocol;
    uint32_t saddr = ntohl(ip->saddr);
    uint32_t daddr = ntohl(ip->daddr);
    uint16_t tot_len = ntohs(ip->tot_len);
    unsigned int sport = 0, dport = 0, tcp_flags = 0;

    const unsigned char *l4 = data + ihl;
    int l4_len = len - ihl;

    if (proto == IPPROTO_TCP && l4_len >= 14) {
        sport = (l4[0] << 8) | l4[1];
        dport = (l4[2] << 8) | l4[3];
        tcp_flags = l4[13]; // TCP Control Bits
    } else if (proto == IPPROTO_UDP && l4_len >= 8) {
        sport = (l4[0] << 8) | l4[1];
        dport = (l4[2] << 8) | l4[3];
        tcp_flags = 0;
    } else {
        return;
    }

    // Output strictly non-payload header record:
    printf("%ld.%06ld %u %08x %08x %u %u %u %u\n",
           tv.tv_sec, tv.tv_usec, proto, saddr, daddr, sport, dport, tot_len, tcp_flags);
    fflush(stdout);
}

int main(void) {
    int fd = socket(AF_NETLINK, SOCK_RAW, NETLINK_NETFILTER);
    if (fd < 0) {
        perror("socket(NETLINK_NETFILTER)");
        return 1;
    }

    struct sockaddr_nl sa;
    memset(&sa, 0, sizeof(sa));
    sa.nl_family = AF_NETLINK;
    sa.nl_pid = getpid();
    sa.nl_groups = 0;

    if (bind(fd, (struct sockaddr *)&sa, sizeof(sa)) < 0) {
        perror("bind");
        close(fd);
        return 1;
    }

    int bufsiz = 524288;
    setsockopt(fd, SOL_SOCKET, SO_RCVBUF, &bufsiz, sizeof(bufsiz));

    char buf[BUFSIZE];
    while (1) {
        ssize_t len = recv(fd, buf, sizeof(buf), 0);
        if (len < 0) {
            perror("recv");
            break;
        }

        struct nlmsghdr *nlh = (struct nlmsghdr *)buf;
        while (NLMSG_OK(nlh, len)) {
            if (nlh->nlmsg_type == NLMSG_ERROR) {
                break;
            }

            struct nfgenmsg *nfm = (struct nfgenmsg *)NLMSG_DATA(nlh);
            struct nlattr *nla = (struct nlattr *)((char *)nfm + sizeof(struct nfgenmsg));
            int nla_len = nlh->nlmsg_len - NLMSG_LENGTH(sizeof(struct nfgenmsg));

            while (NLA_OK(nla, nla_len)) {
                uint16_t type = nla->nla_type & NLA_TYPE_MASK;
                if (type == NFULA_PAYLOAD) {
                    process_packet((const unsigned char *)NLA_DATA(nla), NLA_PAYLOAD(nla));
                }
                nla = NLA_NEXT(nla, nla_len);
            }

            nlh = NLMSG_NEXT(nlh, len);
        }
    }

    close(fd);
    return 0;
}
