# Admin-managed sellers, dealerships, and account claiming

Status: implementation design; not enabled in production.

## Goals
- Admin can create a managed individual or dealership seller profile without a login.
- Admin can publish vehicles on behalf of that seller while preserving existing validation, image minimum, and contact rules.
- A seller may register independently and request to claim an existing managed profile.
- Admin verifies the claim and grants control without changing vehicle IDs, deleting images, or losing inquiries.
- After claiming, seller controls whether Carvion may continue routine listing management; assistance defaults OFF.
- Platform moderation always remains available to admins.

## Existing constraints (main branch)
- `cars.seller_id` is a required foreign key to `users.id`.
- `inquiries.seller_id` also requires a real user.
- `dealerships.owner_id` is required, unique, and references users.
- Public dealership showroom queries cars using `seller_id == dealership.owner_id`.
- User accounts require email and password. Do not create fabricated login credentials for virtual sellers.
- Production runs PostgreSQL and uses `db.create_all()`; adding columns requires an explicit migration.

## Proposed data model
- `seller_profiles`: id, kind (individual/dealership), display_name, public_contact, private_contact, location, status (managed/claimed), claimed_by_user_id nullable, assistance_enabled default false, consent record, created_by_admin_id, timestamps.
- `cars.seller_profile_id` nullable during backwards-compatible rollout; all new assisted listings require it. Keep legacy `seller_id` during migration and avoid rewriting existing listing ownership until proven safe.
- `dealerships.seller_profile_id` nullable unique for unified showrooms. Existing dealership owner links remain functional.
- `profile_claim_requests`: profile_id, requesting_user_id, status, evidence metadata, reviewed_by_admin_id, timestamps.
- `profile_audit_events`: actor_user_id, seller_profile_id, action, timestamps, minimal safe metadata.

## Permissions and workflow
1. Admin creates seller profile, records authorization to advertise, and adds car through existing upload/validation pipeline.
2. Public pages show actual seller, not uploader. Contact preferences control exposed details.
3. Seller registers using normal authentication and requests a claim.
4. Admin verifies authority out of band and approves once, transactionally; prevent multiple active claims.
5. Claimed seller can manage their own listings. Assistance starts disabled and can be explicitly enabled or disabled at any time.
6. Admin assisted edits require assistance permission; admin moderation is separately authorized.
7. Claims must never transfer passwords, reset tokens, other seller's vehicles, or private messages to a different person.

## Required engineering sequence
1. Create and test reversible Alembic migrations; backup PostgreSQL before deployment.
2. Implement profile model and permissions service; adapt vehicle and inquiry ownership resolution.
3. Implement admin create/list/edit seller profiles, admin-assisted vehicle upload, and dealership integration.
4. Implement authenticated claim request, admin review, and seller assistance setting.
5. Update public listing/showroom/contact and dashboards; preserve current dealer URLs.
6. Add regression tests: legacy listings, five-image validation, duplicate registration, claim authorization, concurrent claims, revoked assistance, inquiries, delete safety.
7. Run CI and staging tests, then merge and deploy only after verification.

## Non-goals
- No automatic verification badge just because admin uploaded a car.
- No transfer of account credentials.
- No direct modification of production database from this design document.
