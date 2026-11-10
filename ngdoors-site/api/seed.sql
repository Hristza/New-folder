-- First admins. No password yet: each sets one through the emailed link (POST /auth/reset).
insert or ignore into admins (email) values ('ngbuildings@abv.bg'), ('hrisodim0@gmail.com');
