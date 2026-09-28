# Engineering Onboarding Guide

This guide is for engineers joining Northwind Analytics. Read the Employee Handbook first; this guide only covers what is specific to engineering teams.

## Your First Week

On your first day you receive a laptop with the standard developer image. Your buddy will pair with you on a small starter ticket so that you ship code to production within your first five working days. By the end of the week you should have access to source control, the CI system, the staging environment and the team's on-call calendar.

## Development Environment

### Laptop Setup

Engineering laptops come with 32 GB of memory and full disk encryption enabled. Install the developer tools from the self-service portal rather than downloading them yourself, so that security updates are applied automatically. Local administrator rights are granted for 30 days at a time and can be renewed through the IT helpdesk.

### Engineering VPN Profile

Engineers use the same VPN client as everyone else but connect with a dedicated profile that also routes traffic to the staging network:

```bash
nwvpn connect --region eu-central --profile engineering
nwvpn routes --show
```

The engineering profile keeps a session for 12 hours before asking you to log in again.

## Code Review and Deployment

Every change needs one approving review before it is merged, and changes to payment or authentication code need two. Deployments to production happen through the pipeline only; nobody deploys from a laptop. Production deployments are paused on Fridays after 15:00 and during company-wide events.

| Environment | Deploys | Who can approve |
|---|---|---|
| Staging | Automatically on merge | Any engineer |
| Production | Manually from the pipeline | Team lead or on-call engineer |
| Hotfix | Any time, with incident ticket | On-call engineer |

## On-Call

Engineers join the on-call rotation after their third month. A rotation lasts one week, from Monday 10:00 to the following Monday 10:00, and you are paid an on-call allowance of €250 per week plus €50 for every night you are paged. If you cannot respond to a page within 15 minutes, hand over to the secondary on-call engineer through the paging tool.

## Security Expectations

- Never store customer data on your laptop, not even for debugging.
- Secrets live in the vault; API keys in source control are treated as a security incident.
- Report a suspected security issue in the #security channel, or to security@northwind.example outside working hours.
