using UnityEngine;

namespace SwordsmanTest
{
    // Impact sparks and flash on the struck target, driven by the player's public combat state.
    // Sounds were removed on purpose until proper recorded clips are chosen.
    public class SlashFeedback : MonoBehaviour
    {
        CombatPlayer player; SwordRibbon ribbon;
        ParticleSystem sparks, flash;
        int lastHits;
        int[] targetHits = new int[0];

        public void Initialize(CombatPlayer owner, SwordRibbon sweep)
        {
            player = owner; ribbon = sweep;
            if (ribbon && ribbon.material)
            {
                var particleMaterial = new Material(ribbon.material) { name = "Slash sparks (runtime)" };
                particleMaterial.SetFloat("_Spark", 1);
                sparks = Particles("Slash sparks", particleMaterial, true);
                flash = Particles("Slash impact flash", particleMaterial, false);
            }
            if (player) { lastHits = player.TotalHits; RememberTargetHits(); }
        }

        public void Tick(float dt)
        {
            if (!player) return;
            if (player.TotalHits < lastHits) lastHits = player.TotalHits; // arena reset
            if (player.TotalHits > lastHits)
            {
                lastHits = player.TotalHits;
                Burst(player.State == "attack_3" || player.State == "piercing_lunge", ImpactPoint());
            }
            RememberTargetHits();
        }

        // The hit test is an arc around the hero, so the blade tip may still be overhead at contact:
        // put sparks on the struck target's surface, facing the hero.
        Vector3 ImpactPoint()
        {
            var targets = player.targets;
            for (int i = 0; targets != null && i < targets.Length; i++)
            {
                if (!targets[i] || i >= targetHits.Length || targets[i].Hits <= targetHits[i]) continue;
                Vector3 toHero = Vector3.ProjectOnPlane(player.transform.position - targets[i].transform.position, Vector3.up).normalized;
                return targets[i].transform.position + Vector3.up * .95f + toHero * .38f;
            }
            return ribbon && ribbon.bladeTip ? ribbon.TipPoint : player.transform.position + Vector3.up;
        }

        void RememberTargetHits()
        {
            var targets = player.targets; int n = targets != null ? targets.Length : 0;
            if (targetHits.Length != n) targetHits = new int[n];
            for (int i = 0; i < n; i++) targetHits[i] = targets[i] ? targets[i].Hits : 0;
        }

        void Burst(bool heavy, Vector3 point)
        {
            if (!sparks) return;
            Color colour = SwordRibbon.Palette(player.State, Color.white);
            var emit = new ParticleSystem.EmitParams { position = point, applyShapeToPosition = true };
            int count = heavy ? 34 : 18;
            for (int i = 0; i < count; i++)
            {
                emit.velocity = (Random.onUnitSphere + Vector3.up * .6f).normalized * Random.Range(4f, heavy ? 12f : 8f);
                emit.startColor = Color.Lerp(colour, Color.white, Random.value * .6f);
                emit.startSize = Random.Range(.03f, heavy ? .08f : .06f);
                emit.startLifetime = Random.Range(.16f, .34f);
                sparks.Emit(emit, 1);
            }
            flash.Emit(new ParticleSystem.EmitParams { position = point, velocity = Vector3.zero, startColor = colour,
                startSize = heavy ? 1.9f : 1.1f, startLifetime = .09f }, 1);
        }

        ParticleSystem Particles(string name, Material material, bool stretched)
        {
            var host = new GameObject(name);
            var system = host.AddComponent<ParticleSystem>();
            system.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = system.main; main.playOnAwake = false; main.loop = false; main.maxParticles = 160;
            main.simulationSpace = ParticleSystemSimulationSpace.World; main.gravityModifier = stretched ? 1.4f : 0;
            var emission = system.emission; emission.rateOverTime = 0;
            var shape = system.shape; shape.shapeType = ParticleSystemShapeType.Sphere; shape.radius = .04f;
            var fade = system.colorOverLifetime; fade.enabled = true;
            var gradient = new Gradient();
            gradient.SetKeys(new[] { new GradientColorKey(Color.white, 0), new GradientColorKey(Color.white, 1) },
                new[] { new GradientAlphaKey(1, 0), new GradientAlphaKey(stretched ? .8f : .5f, .4f), new GradientAlphaKey(0, 1) });
            fade.color = gradient;
            if (!stretched)
            {
                var grow = system.sizeOverLifetime; grow.enabled = true; grow.size = new ParticleSystem.MinMaxCurve(1, AnimationCurve.EaseInOut(0, .55f, 1, 1.25f));
            }
            var renderer = host.GetComponent<ParticleSystemRenderer>(); renderer.sharedMaterial = material;
            renderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off; renderer.receiveShadows = false;
            if (stretched) { renderer.renderMode = ParticleSystemRenderMode.Stretch; renderer.velocityScale = .045f; renderer.lengthScale = 1.2f; }
            system.Play();
            return system;
        }
    }
}
