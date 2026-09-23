## Decision

Shared schema + tenant_id column on every tenant-owned table (filter every query).

## Context

Tenants should be limited from accessing other tenants' information; failing this leads to
data leaks / security incidents / loss of confidence in the product.

## Requirements

The requirement here is that, for security reasons, one tenant must not be able to get
another tenant's information. Resolving the tenant id from the JWT token guarantees tenant
isolation.

## Options

1. Shared schema + tenant_id column on every tenant-owned table (filter every query). (chosen option)
2. Schema-per-tenant. Rejected (makes migrations difficult).
3. Database-per-tenant. Rejected (makes persistence complicated + expensive).

## Why

Saves the cost of maintaining multiple databases; also makes migrations less painful.

## Trade-offs

- As the number of tenants gets big we might experience performance degradation on queries.

## Failure modes

We should enforce that without the tenant filter no data is returned; no endpoint should be
able to return data across all tenants (testing).
The tenant always comes from the JWT; no endpoint should accept a tenant id.
In case of a missing JWT, reject the request (request filtering).
Enforced via a repository base that always injects the tenant filter, so normal queries can't omit it; cross-tenant access requires an explicit, separately-named 
method; tests act as a backstop.

## Consequences

Each tenant is only able to access their own data from the repository.

## When we would reconsider this decision

If the number of records forces us to separate the data into different databases, e.g.
querying becomes very slow.
