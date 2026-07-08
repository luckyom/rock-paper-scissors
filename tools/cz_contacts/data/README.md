# Seed CSVs

Drop optional seed lists here. Each is `organization,city,website,events`
(header row required; `website` and `events` may be blank). The crawler merges
them with its built-in discovery and scrapes every email from the live sites —
seeds never contain emails.

| file | purpose |
|------|---------|
| `venues.csv` | extra Kulturní domy / MKS not found via NIPOS |
| `xmas.csv` | Christmas-market organizer sites you've identified by search |
| `festivals.csv` | city festivals / vinobraní organizers (pořadatel → site) |
| `agencies.csv` | additional live-music booking agencies |
| `weddings.csv` | additional wedding agencies / coordinators / venues |

`*.example.csv` files show the format. Copy one to the real name to use it.
