from hcloud.firewalls import FirewallRule, BoundFirewall

import helpers as hlp

rules = [
    FirewallRule(direction='in', protocol='tcp', port='22', source_ips=['0.0.0.0/0', '::/0']),
    FirewallRule(direction='in', protocol='tcp', port='80', source_ips=['0.0.0.0/0', '::/0']),
    FirewallRule(direction='in', protocol='tcp', port='443', source_ips=['0.0.0.0/0', '::/0']),
]

if isinstance(hlp.cli.firewalls.get_by_name('tps-firewall'), BoundFirewall):
    hlp.cli.firewalls.create(name='tps-firewall', rules=rules)
