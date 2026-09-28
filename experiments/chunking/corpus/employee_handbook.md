---
title: Northwind Employee Handbook
author: People Operations
date: 2026-03-01
---

# Northwind Employee Handbook

Welcome to Northwind Analytics. This handbook explains how we work, what we offer, and what we expect from everyone on the team. It applies to all full-time and part-time employees in every office. Contractors follow the terms of their own agreements.

## Working Hours and Remote Work

Core collaboration hours are 10:00 to 15:00 in your local time zone. Outside of core hours you may arrange your day as you see fit, as long as your team knows how to reach you. Employees may work remotely up to three days per week. Fully remote arrangements require written approval from both your manager and the People Operations team, and they are reviewed every six months.

When working remotely you must use a secured home network. Public Wi-Fi in cafés, airports or hotels may only be used together with the company VPN.

## Leave Policy

### Annual Leave

Full-time employees receive 25 days of paid annual leave per calendar year, plus public holidays. Part-time employees receive leave pro rata to their contracted hours. Up to five unused days can be carried over into the next year, but carried-over days expire on 31 March.

Leave requests must be submitted in the HR portal at least two weeks in advance for absences longer than three consecutive days.

### Leave Types at a Glance

| Leave type | Paid days per year | Approval needed from |
|---|---|---|
| Annual leave | 25 | Line manager |
| Sick leave | 12 | None for up to 2 days, then a doctor's note |
| Parental leave | 90 | People Operations |
| Bereavement leave | 5 | Line manager |
| Volunteering day | 2 | Line manager |

### Sick Leave

If you are ill, notify your manager before 09:30 on the first day of absence. For absences longer than two consecutive days, a doctor's note must be uploaded to the HR portal. Sick days do not reduce your annual leave balance.

## Expenses and Travel

Business travel must be booked through the TravelDesk tool so that the company can locate employees in an emergency. Economy class is the standard for all flights under six hours; premium economy is allowed for longer flights. Hotel costs are reimbursed up to €180 per night in Europe and up to $220 per night in North America.

Meals during business travel are covered up to a daily allowance of €60. Alcohol is never reimbursed. Receipts must be submitted within 30 days of the expense, otherwise the claim is rejected automatically.

## IT and Security

### Connecting to the VPN

All access to internal systems requires the corporate VPN. Install the client from the self-service portal, then connect from a terminal:

```bash
nwvpn login --sso
nwvpn connect --region eu-central --profile staff
nwvpn status
```

If `nwvpn status` reports "degraded", switch to the backup region with `--region eu-west` and contact the IT helpdesk at extension 4400.

### Passwords and Devices

- Passwords must be at least 14 characters long.
- Multi-factor authentication is mandatory for email, the HR portal and source control.
- Laptops lock automatically after 5 minutes of inactivity.
- Lost or stolen devices must be reported to security@northwind.example within one hour.

## Learning and Development

Every employee has an annual learning budget of €1,500 that can be spent on courses, conferences and books. Budget that is not used by 31 December does not roll over. Requests above €500 need approval from your manager, and conference trips also count against the travel policy above.
