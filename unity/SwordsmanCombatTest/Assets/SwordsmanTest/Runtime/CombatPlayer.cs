using System;
using System.Collections.Generic;
using UnityEngine;

namespace SwordsmanTest
{
    [Serializable]
    public struct CombatInput
    {
        public Vector2 move;
        public Vector3 aim;
        public bool attack, dodge, lunge, reset;
    }

    [DefaultExecutionOrder(-100)]
    public class CombatPlayer : MonoBehaviour
    {
        public CombatTuning tuning;
        public CharacterController motor;
        public CombatAnimation animationPlayer;
        public Camera gameCamera;
        public CombatCamera cameraRig;
        public TrailRenderer bladeTrail;
        public SwordRibbon swordRibbon;
        public DashGhosts dashGhosts;
        public LineRenderer hitboxOutline;
        public TrainingDummy[] targets;
        public bool externalDrive, showHitboxes = true;
        public string State { get; private set; } = "locomotion";
        public float ActionTime { get; private set; }
        public float DodgeCooldown { get; private set; }
        public float LungeCooldown { get; private set; }
        public float SimulationDelta { get; private set; }
        public float Health { get; private set; } = 100;
        public int TotalHits { get; private set; }
        public int StartedMoves { get; private set; }
        public int DodgeCancels { get; private set; }
        public bool ComboQueued => comboQueued;
        public bool Invulnerable => State == "dodge" && ActionTime >= move.invulnerableStart && ActionTime < move.invulnerableEnd;
        public bool Active => move != null && ActionTime >= move.activeStart && ActionTime <= move.activeEnd && move.activeEnd > move.activeStart;
        public string Phase => State == "locomotion" ? "MOVE" : ActionTime < move.activeStart ? "STARTUP" : Active ? "ACTIVE" : "RECOVERY";
        public MoveDefinition CurrentMove => move;
        readonly Collider[] overlaps = new Collider[64];
        readonly HashSet<TrainingDummy> hitTargets = new HashSet<TrainingDummy>();
        MoveDefinition move;
        Vector3 velocity, actionDirection, spawn, carry;
        float locomotionTime, idleTime, freeze, attackBuffer, carryDecel, actionBlend;
        bool comboQueued, initialized;

        public void Initialize()
        {
            if (initialized) return;
            initialized = true; spawn = transform.position;
            tuning = Instantiate(tuning); // Game-view sliders should not mutate the project asset.
            if (!gameCamera) gameCamera = Camera.main;
            if (!cameraRig && gameCamera) cameraRig = gameCamera.GetComponent<CombatCamera>();
            if (targets == null || targets.Length == 0) targets = FindObjectsByType<TrainingDummy>();
            animationPlayer.Initialize();
            foreach (var dummy in targets) dummy.Initialize();
            animationPlayer.Sample("idle", 0, 1);
        }
        void Start() { Initialize(); }

        void Update()
        {
            if (externalDrive) return;
            if (Input.GetKeyDown(KeyCode.V)) showHitboxes = !showHitboxes;
            if (Input.GetKeyDown(KeyCode.H)) TryDamage(10);
            var input = new CombatInput
            {
                move = Vector2.ClampMagnitude(new Vector2((Input.GetKey(KeyCode.D) ? 1 : 0) - (Input.GetKey(KeyCode.A) ? 1 : 0),
                    (Input.GetKey(KeyCode.W) ? 1 : 0) - (Input.GetKey(KeyCode.S) ? 1 : 0)), 1),
                aim = MouseAim(),
                attack = Input.GetMouseButtonDown(0) && !CombatHUD.PointerOverPanel(),
                dodge = Input.GetKeyDown(KeyCode.Space) || Input.GetKeyDown(KeyCode.LeftShift),
                lunge = Input.GetKeyDown(KeyCode.E) || Input.GetMouseButtonDown(1),
                reset = Input.GetKeyDown(KeyCode.R)
            };
            Tick(Mathf.Min(Time.unscaledDeltaTime, .05f), input);
        }

        public Vector3 MouseAim()
        {
            Ray ray = gameCamera.ScreenPointToRay(Input.mousePosition);
            var plane = new Plane(Vector3.up, Vector3.zero);
            return plane.Raycast(ray, out float distance) ? ray.GetPoint(distance) : transform.position + transform.forward;
        }
        public Vector3 CameraMove(Vector2 input)
        {
            Vector3 forward = Vector3.ProjectOnPlane(gameCamera.transform.forward, Vector3.up).normalized;
            Vector3 right = Vector3.ProjectOnPlane(gameCamera.transform.right, Vector3.up).normalized;
            return Vector3.ClampMagnitude(forward * input.y + right * input.x, 1);
        }

        public void ResetArena()
        {
            Initialize(); motor.enabled = false; transform.position = spawn; transform.rotation = Quaternion.identity; motor.enabled = true;
            foreach (var dummy in targets) dummy.ResetDummy();
            velocity = carry = Vector3.zero; State = "locomotion"; move = null; ActionTime = 0;
            DodgeCooldown = LungeCooldown = freeze = attackBuffer = 0; comboQueued = false; Health = 100;
            TotalHits = StartedMoves = DodgeCancels = 0;
            if (bladeTrail) { bladeTrail.emitting = false; bladeTrail.Clear(); }
            animationPlayer.Sample("idle", 0, 1); Physics.SyncTransforms();
            if (cameraRig) cameraRig.Snap();
        }

        public void Teleport(Vector3 position, Vector3 facing)
        {
            motor.enabled = false; transform.position = position; motor.enabled = true;
            if (facing.sqrMagnitude > .001f) transform.rotation = Quaternion.LookRotation(facing);
            Physics.SyncTransforms();
        }

        public bool TryDamage(float amount)
        {
            if (Invulnerable || State == "death") return false;
            Health = Mathf.Max(0, Health - amount);
            StartMove(Health <= 0 ? "death" : "hurt", transform.forward);
            return true;
        }

        void StartMove(string id, Vector3 direction)
        {
            State = id; move = tuning.Get(id); ActionTime = 0;
            actionDirection = Vector3.ProjectOnPlane(direction, Vector3.up).normalized;
            if (actionDirection.sqrMagnitude < .1f) actionDirection = transform.forward;
            transform.rotation = Quaternion.LookRotation(actionDirection);
            comboQueued = false; attackBuffer = 0; hitTargets.Clear(); StartedMoves++;
            carry = Vector3.zero; actionBlend = 0;
            if (bladeTrail) bladeTrail.Clear();
        }

        public void Tick(float dt, CombatInput input)
        {
            Initialize(); if (input.reset) { ResetArena(); return; }
            Vector3 movement = CameraMove(input.move);
            Vector3 aim = Vector3.ProjectOnPlane(input.aim - transform.position, Vector3.up).normalized;
            if (aim.sqrMagnitude < .1f) aim = transform.forward;
            DodgeCooldown = Mathf.Max(0, DodgeCooldown - dt); LungeCooldown = Mathf.Max(0, LungeCooldown - dt);
            attackBuffer = Mathf.Max(0, attackBuffer - dt);
            bool attacking = State.StartsWith("attack_", StringComparison.Ordinal);
            if (input.attack && attacking) attackBuffer = .16f;
            if (attacking && ActionTime >= move.bufferStart && attackBuffer > 0) comboQueued = true;
            bool canCancel = attacking && tuning.allowRecoveryDodgeCancel && ActionTime >= move.cancelStart;
            if (input.dodge && DodgeCooldown <= 0 && (State == "locomotion" || canCancel))
            {
                if (canCancel) DodgeCancels++;
                StartMove("dodge", movement.sqrMagnitude > .01f ? movement : transform.forward);
                DodgeCooldown = tuning.dodgeCooldown;
            }
            else if (input.lunge && LungeCooldown <= 0 && State == "locomotion")
            {
                StartMove("piercing_lunge", aim); LungeCooldown = tuning.lungeCooldown;
            }
            else if (input.attack && State == "locomotion")
            {
                Vector3 runVelocity = velocity;
                StartMove("attack_1", aim);
                // A strike started from a run keeps the stride's momentum and bleeds it off over the wind-up.
                if (runVelocity.magnitude > 1)
                {
                    carry = runVelocity * tuning.runAttackCarry;
                    float stop = tuning.runAttackStopTime * (Vector3.Dot(runVelocity, actionDirection) < 0 ? .5f : 1);
                    carryDecel = carry.magnitude / Mathf.Max(.01f, stop);
                    actionBlend = tuning.runAttackBlend;
                }
            }

            SimulationDelta = freeze > 0 ? 0 : dt;
            freeze = Mathf.Max(0, freeze - dt);
            float step = SimulationDelta;
            if (State == "locomotion")
            {
                Vector3 desired = movement * tuning.runSpeed;
                velocity = Vector3.MoveTowards(velocity, desired, tuning.acceleration * step);
                motor.Move((velocity + Vector3.down * 2) * step);
                if (movement.sqrMagnitude > .01f) transform.rotation = Quaternion.RotateTowards(transform.rotation,
                    Quaternion.LookRotation(movement), tuning.turnSpeed * step);
                locomotionTime += step * velocity.magnitude / tuning.runReferenceSpeed; idleTime += step;
                bool running = velocity.magnitude > .15f;
                animationPlayer.Sample(running ? "run" : "idle", running ? locomotionTime : idleTime, step, .10f);
            }
            else
            {
                velocity = Vector3.zero;
                float before = ActionTime;
                ActionTime = Mathf.Min(ActionTime + step, move.duration);
                Vector3 oldPosition = transform.position;
                float interval = move.travelEnd - move.travelStart;
                float fraction = interval > 0 ? (Mathf.Clamp(ActionTime, move.travelStart, move.travelEnd) -
                    Mathf.Clamp(before, move.travelStart, move.travelEnd)) / interval : 0;
                carry = Vector3.MoveTowards(carry, Vector3.zero, carryDecel * step);
                motor.Move((actionDirection * (move.travelDistance * fraction)) + carry * step + Vector3.down * (2 * step));
                animationPlayer.Sample(State, ActionTime, step, actionBlend > 0 ? actionBlend : attacking ? .035f : .06f);
                Physics.SyncTransforms();
                if (move.activeEnd > move.activeStart && ActionTime >= move.activeStart && before <= move.activeEnd)
                    ResolveHits(oldPosition, actionDirection);
                if (State != "death" && ActionTime >= move.duration)
                {
                    if (comboQueued && State == "attack_1") StartMove("attack_2", actionDirection);
                    else if (comboQueued && State == "attack_2") StartMove("attack_3", actionDirection);
                    else { State = "locomotion"; move = null; comboQueued = false; }
                }
            }
            foreach (var dummy in targets) dummy.Tick(step);
            if (bladeTrail)
            {
                bladeTrail.emitting = Active;
                Color color = State == "attack_3" ? new Color(1, .28f, .07f, .8f) :
                    State == "piercing_lunge" ? new Color(.25f, .9f, 1, .8f) : new Color(1, .72f, .25f, .7f);
                bladeTrail.startColor = color; bladeTrail.endColor = new Color(color.r, color.g, color.b, 0);
            }
            if(swordRibbon)
            {
                bool sweep=move!=null && move.activeEnd>move.activeStart && ActionTime>=move.activeStart-.02f && ActionTime<=move.activeEnd+.07f;
                Color colour=State=="attack_3"?new Color(1,.87f,.60f,.8f):State=="piercing_lunge"?new Color(.65f,.94f,1,.65f):new Color(.94f,.97f,1,.65f);
                swordRibbon.Tick(step,sweep,colour);
            }
            if(dashGhosts)dashGhosts.Tick(step,State=="dodge" && ActionTime>.055f && ActionTime<.25f);
            DrawHitbox();
        }

        void ResolveHits(Vector3 previousPosition, Vector3 direction)
        {
            Vector3 origin = transform.position + Vector3.up * .85f;
            bool thrust = State == "piercing_lunge";
            int count = thrust ? Physics.OverlapCapsuleNonAlloc(previousPosition + Vector3.up * .85f,
                origin + direction * move.reach, .43f, overlaps, ~0, QueryTriggerInteraction.Collide) :
                Physics.OverlapSphereNonAlloc(origin, move.reach + .3f, overlaps, ~0, QueryTriggerInteraction.Collide);
            for (int i = 0; i < count; i++)
            {
                var dummy = overlaps[i].GetComponentInParent<TrainingDummy>();
                if (!dummy || hitTargets.Contains(dummy) || dummy.Health <= 0) continue;
                Vector3 delta = Vector3.ProjectOnPlane(dummy.transform.position - transform.position, Vector3.up);
                if (!thrust && (delta.magnitude > move.reach + .3f ||
                    Vector3.Angle(direction, delta) > move.arc * .5f)) continue;
                // Solid arena props block damage through walls; dummies use trigger hurtboxes.
                Vector3 destination = dummy.transform.position + Vector3.up * .85f;
                if (Physics.Linecast(origin, destination, out RaycastHit obstruction, ~0, QueryTriggerInteraction.Ignore) &&
                    obstruction.collider != motor) continue;
                hitTargets.Add(dummy); dummy.Hit(move.damage, direction, move.knockback); TotalHits++;
                freeze = Mathf.Max(freeze, move.hitstop);
                if (cameraRig) cameraRig.Shake(State == "attack_3" ? .10f : State == "piercing_lunge" ? .065f : .022f);
            }
        }

        void DrawHitbox()
        {
            if (!hitboxOutline) return;
            hitboxOutline.enabled = showHitboxes && (Active || Invulnerable);
            if (!hitboxOutline.enabled) return;
            Color color = Invulnerable ? Color.cyan : new Color(1, .42f, .10f);
            hitboxOutline.startColor = hitboxOutline.endColor = color;
            int n = 32; hitboxOutline.positionCount = n + 3;
            Vector3 origin = transform.position + Vector3.up * .035f;
            float arc = Invulnerable ? 360 : move.arc;
            float reach = Invulnerable ? .45f : move.reach;
            hitboxOutline.SetPosition(0, origin);
            for (int i = 0; i <= n; i++)
            {
                Vector3 direction = Quaternion.AngleAxis(-arc / 2 + arc * i / n, Vector3.up) * transform.forward;
                hitboxOutline.SetPosition(i + 1, origin + direction * reach);
            }
            hitboxOutline.SetPosition(n + 2, origin);
        }
    }
}
