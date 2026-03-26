const STATES = { SPAWN: 0, WALK: 1, ATTACK: 2, REACHED_BASE: 3, DEAD: 4 };

class FSM {
    constructor() { this.state = STATES.SPAWN; this.timer = 0; }
    update(enemy, towers) {
        if (enemy.health <= 0) { this.state = STATES.DEAD; return; }
        switch (this.state) {
            case STATES.SPAWN: 
                if (this.timer++ > 20) this.state = STATES.WALK; break;
            case STATES.WALK: 
                enemy.x -= enemy.speed; 
                if (enemy.x <= 50) { this.state = STATES.REACHED_BASE; return; }
                for (let i = 0; i < towers.length; i++) {
                    let t = towers[i];
                    if (Math.abs(enemy.x - t.x) < 40 && Math.abs(enemy.y - t.y) < 40) {
                        enemy.targetTower = t; this.state = STATES.ATTACK; break;
                    }
                }
                break;
            case STATES.ATTACK:
                if (!towers.includes(enemy.targetTower)) this.state = STATES.WALK;
                else enemy.targetTower.health -= 1;
                break;
            case STATES.REACHED_BASE: 
                enemy.health = 0; this.state = STATES.DEAD; break;
        }
    }
}