class Tower {
    constructor(x, y) {
        this.x = x; this.y = y; this.width = 50; this.height = 50;
        this.health = 100; this.cooldown = 0; this.range = 350;
    }
    update(enemies, bullets, playSound) {
        this.cooldown--;
        if (this.cooldown <= 0 && enemies.length > 0) {
            let closest = enemies[0];
            if (closest.x - this.x < this.range && closest.x > this.x) {
                bullets.push(new Bullet(this.x + 25, this.y + 25));
                this.cooldown = 40; playSound('shoot');
            }
        }
    }
    draw(ctx, img) {
        if (img && img.complete && img.naturalHeight !== 0) { ctx.drawImage(img, this.x, this.y, this.width, this.height); }
        else { ctx.font = '45px Arial'; ctx.fillText('🗼', this.x + 2, this.y + 40); }
        ctx.fillStyle = 'red'; ctx.fillRect(this.x, this.y + 45, 50, 5);
        ctx.fillStyle = '#3498db'; ctx.fillRect(this.x, this.y + 45, 50 * (this.health/100), 5);
    }
}

class Bullet {
    constructor(x, y) { this.x = x; this.y = y; this.speed = 8; this.damage = 25; }
    update() { this.x += this.speed; }
    draw(ctx) { ctx.fillStyle = '#f1c40f'; ctx.beginPath(); ctx.arc(this.x, this.y, 6, 0, Math.PI*2); ctx.fill(); }
}