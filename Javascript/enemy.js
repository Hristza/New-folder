class Enemy {
    constructor(x, y, level) {
        this.x = x; this.y = y; this.width = 40; this.height = 40;
        this.maxHealth = 30 + (level * 10); this.health = this.maxHealth; 
        this.speed = 1 + (level * 0.2) + Math.random();
        this.fsm = new FSM(); this.targetTower = null;
    }
    update(towers) { this.fsm.update(this, towers); }
    draw(ctx, img) {
        if (img && img.complete && img.naturalHeight !== 0) { ctx.drawImage(img, this.x, this.y, this.width, this.height); }
        else { ctx.font = '40px Arial'; ctx.fillText('🧟', this.x, this.y + 35); }
        ctx.fillStyle = 'red'; ctx.fillRect(this.x, this.y - 10, 40, 5);
        ctx.fillStyle = '#2ecc71'; ctx.fillRect(this.x, this.y - 10, 40 * (this.health/this.maxHealth), 5);
    }
}