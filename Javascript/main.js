const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

let towers = []; let enemies = []; let bullets = [];
let money = 150; let level = 1; let enemiesToSpawn = 5; let frames = 0;
let gameState = 'START'; let mouseX = 0; let mouseY = 0;

const imgTower = new Image(); imgTower.src = 'assets/images/tower.png';
const imgEnemy = new Image(); imgEnemy.src = 'assets/images/enemy.png';

function playSound(type) {
    try {
        let audio = new Audio('assets/sounds/' + type + '.wav');
        if (type === 'bgm') audio = new Audio('assets/sounds/bgm.mp3');
        audio.volume = 0.5;
        audio.play().catch(e => {});
    } catch(e) {}
}

document.getElementById('startBtn').onclick = function() {
    document.getElementById('startMenu').style.display = 'none';
    gameState = 'PLAYING';
    playSound('bgm');
    animate();
};

document.getElementById('nextLevelBtn').onclick = function() {
    level++; enemiesToSpawn = 5 + (level * 2); 
    document.getElementById('levelDisplay').innerText = level;
    document.getElementById('levelMenu').style.display = 'none'; 
    gameState = 'PLAYING'; 
    animate();
};

document.getElementById('restartBtn').onclick = function() { location.reload(); };

canvas.onmousemove = function(e) {
    const rect = canvas.getBoundingClientRect(); 
    mouseX = e.clientX - rect.left; mouseY = e.clientY - rect.top;
};

canvas.onclick = function() {
    if (gameState !== 'PLAYING') return;
    if (mouseX > 50 && money >= 50) {
        const gridX = Math.floor(mouseX/50)*50; const gridY = Math.floor(mouseY/50)*50;
        if (!towers.some(t => t.x === gridX && t.y === gridY)) {
            towers.push(new Tower(gridX, gridY)); 
            money -= 50; document.getElementById('moneyDisplay').innerText = money;
        }
    }
};

function animate() {
    if (gameState !== 'PLAYING') return; 
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    ctx.strokeStyle = 'rgba(0,0,0,0.1)'; ctx.lineWidth = 1;
    for(let i=0; i<=canvas.width; i+=50) { ctx.beginPath(); ctx.moveTo(i,0); ctx.lineTo(i,canvas.height); ctx.stroke(); }
    for(let i=0; i<=canvas.height; i+=50) { ctx.beginPath(); ctx.moveTo(0,i); ctx.lineTo(canvas.width,i); ctx.stroke(); }
    ctx.fillStyle = '#2c3e50'; ctx.fillRect(0, 0, 50, canvas.height); 
    if (mouseX > 50) { ctx.fillStyle = 'rgba(255,255,255,0.3)'; ctx.fillRect(Math.floor(mouseX/50)*50, Math.floor(mouseY/50)*50, 50, 50); }

    if (frames % Math.max(30, 100 - level * 5) === 0 && enemiesToSpawn > 0) {
        enemies.push(new Enemy(canvas.width, Math.floor(Math.random() * 10) * 50, level)); enemiesToSpawn--;
    }

    towers = towers.filter(t => t.health > 0);
    towers.forEach(t => { t.update(enemies, bullets, playSound); t.draw(ctx, imgTower); });
    
    bullets.forEach((b, bIndex) => {
        b.update(); b.draw(ctx);
        enemies.forEach((e, eIndex) => {
            if (b.x < e.x + e.width && b.x + 10 > e.x && b.y < e.y + e.height && b.y + 10 > e.y) {
                e.health -= b.damage; setTimeout(() => bullets.splice(bIndex, 1), 0);
            }
        });
        if (b.x > canvas.width) setTimeout(() => bullets.splice(bIndex, 1), 0);
    });

    enemies.forEach((e, index) => {
        e.update(towers); e.draw(ctx, imgEnemy);
        if (e.fsm.state === STATES.DEAD) {
            if (e.health > 0) { 
                gameState = 'GAMEOVER'; document.getElementById('gameOverMenu').style.display = 'flex'; playSound('lose');
            } else { 
                money += 20; document.getElementById('moneyDisplay').innerText = money; playSound('kill'); 
            }
            setTimeout(() => enemies.splice(index, 1), 0);
        }
    });

    if (enemiesToSpawn === 0 && enemies.length === 0 && gameState === 'PLAYING') {
        gameState = 'NEXT_LEVEL'; document.getElementById('levelMenu').style.display = 'flex';
    }

    frames++; if (gameState === 'PLAYING') requestAnimationFrame(animate);
}