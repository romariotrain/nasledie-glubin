using UnityEngine;

namespace SwordsmanTest
{
    // Swing whoosh, metal impact and sparks, driven by the player's public combat state.
    // Drop real clips into Assets/SwordsmanTest/Resources/SFX/Swing and SFX/Hit to replace the procedural ones.
    public class SlashFeedback : MonoBehaviour
    {
        [Range(0, 1)] public float swingVolume = .55f, impactVolume = .5f;
        [Tooltip("Swing sound leads the active window by this many seconds")] public float swingLead = .045f;
        CombatPlayer player; SwordRibbon ribbon;
        AudioSource swingSource, impactSource;
        AudioClip[] swingClips, hitClips;
        AudioClip lightSwing, heavySwing, thrustSwing, metalHit;
        ParticleSystem sparks, flash;
        int lastMoves, lastHits; bool swung;
        int[] targetHits = new int[0];

        public void Initialize(CombatPlayer owner, SwordRibbon sweep)
        {
            player = owner; ribbon = sweep;
            swingSource = gameObject.AddComponent<AudioSource>(); swingSource.spatialBlend = 0; swingSource.playOnAwake = false;
            impactSource = gameObject.AddComponent<AudioSource>(); impactSource.spatialBlend = 0; impactSource.playOnAwake = false;
            swingClips = Resources.LoadAll<AudioClip>("SFX/Swing");
            hitClips = Resources.LoadAll<AudioClip>("SFX/Hit");
            lightSwing = Whoosh("Procedural light swing", .22f, 700, 2600, 900, 11);
            heavySwing = Whoosh("Procedural heavy swing", .34f, 380, 1700, 520, 23);
            thrustSwing = Whoosh("Procedural thrust", .2f, 1100, 3600, 1500, 37);
            metalHit = MetalHit();
            if (ribbon && ribbon.material)
            {
                var particleMaterial = new Material(ribbon.material) { name = "Slash sparks (runtime)" };
                particleMaterial.SetFloat("_Spark", 1);
                sparks = Particles("Slash sparks", particleMaterial, true);
                flash = Particles("Slash impact flash", particleMaterial, false);
            }
            if (player) { lastMoves = player.StartedMoves; lastHits = player.TotalHits; RememberTargetHits(); }
        }

        public void Tick(float dt)
        {
            if (!player) return;
            if (player.StartedMoves != lastMoves) { lastMoves = player.StartedMoves; swung = false; }
            var move = player.CurrentMove;
            bool swinging = player.State.StartsWith("attack_") || player.State == "piercing_lunge";
            if (swinging && !swung && move != null && player.ActionTime >= move.activeStart - swingLead)
            {
                swung = true;
                var clip = Pick(swingClips, player.State == "attack_3" ? heavySwing : player.State == "piercing_lunge" ? thrustSwing : lightSwing);
                swingSource.pitch = Random.Range(.93f, 1.07f) * (player.State == "attack_2" ? .94f : 1);
                swingSource.PlayOneShot(clip, swingVolume);
            }
            if (player.TotalHits < lastHits) lastHits = player.TotalHits; // arena reset
            if (player.TotalHits > lastHits)
            {
                lastHits = player.TotalHits;
                bool heavy = player.State == "attack_3" || player.State == "piercing_lunge";
                impactSource.pitch = Random.Range(.95f, 1.05f) * (heavy ? .82f : 1);
                impactSource.PlayOneShot(Pick(hitClips, metalHit), impactVolume);
                Burst(heavy, ImpactPoint());
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
            return ribbon && ribbon.bladeTip ? ribbon.bladeTip.position : player.transform.position + Vector3.up;
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
            int count = heavy ? 26 : 14;
            for (int i = 0; i < count; i++)
            {
                emit.velocity = (Random.onUnitSphere + Vector3.up * .6f).normalized * Random.Range(3.5f, heavy ? 10f : 7f);
                emit.startColor = Color.Lerp(colour, Color.white, Random.value * .6f);
                emit.startSize = Random.Range(.025f, .055f);
                emit.startLifetime = Random.Range(.14f, .3f);
                sparks.Emit(emit, 1);
            }
            flash.Emit(new ParticleSystem.EmitParams { position = point, velocity = Vector3.zero, startColor = colour,
                startSize = heavy ? 1.3f : .8f, startLifetime = .075f }, 1);
        }

        ParticleSystem Particles(string name, Material material, bool stretched)
        {
            var host = new GameObject(name);
            var system = host.AddComponent<ParticleSystem>();
            system.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = system.main; main.playOnAwake = false; main.loop = false; main.maxParticles = 128;
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

        static AudioClip Pick(AudioClip[] options, AudioClip fallback) =>
            options != null && options.Length > 0 ? options[Random.Range(0, options.Length)] : fallback;

        // Band-passed noise whose centre sweeps up and back down: the blade cutting air.
        static AudioClip Whoosh(string name, float duration, float startHz, float peakHz, float endHz, int seed)
        {
            const int rate = 44100; int count = (int)(rate * duration); var data = new float[count];
            var random = new System.Random(seed); float low = 0, band = 0, peak = 0;
            for (int i = 0; i < count; i++)
            {
                float t = i / (float)count;
                float centre = t < .38f ? Mathf.Lerp(startHz, peakHz, t / .38f) : Mathf.Lerp(peakHz, endHz, (t - .38f) / .62f);
                float f = 2 * Mathf.Sin(Mathf.PI * centre / rate);
                float noise = (float)(random.NextDouble() * 2 - 1);
                low += f * band; float high = noise - low - .55f * band; band += f * high;
                float envelope = t < .38f ? Mathf.SmoothStep(0, 1, t / .38f) : Mathf.Pow(1 - (t - .38f) / .62f, 1.8f);
                data[i] = band * envelope; peak = Mathf.Max(peak, Mathf.Abs(data[i]));
            }
            return Clip(name, data, rate, peak);
        }

        // Inharmonic ringing partials with a short noise click: steel meeting a target.
        static AudioClip MetalHit()
        {
            const int rate = 44100; float duration = .38f; int count = (int)(rate * duration); var data = new float[count];
            float[] partials = { 1870, 2730, 4110, 5390, 760 }, decays = { .22f, .16f, .1f, .07f, .09f }, gains = { 1, .7f, .45f, .3f, .9f };
            var random = new System.Random(5); float peak = 0;
            for (int i = 0; i < count; i++)
            {
                float t = i / (float)rate, sample = 0;
                for (int p = 0; p < partials.Length; p++) sample += Mathf.Sin(2 * Mathf.PI * partials[p] * t) * gains[p] * Mathf.Exp(-t / decays[p]);
                sample += (float)(random.NextDouble() * 2 - 1) * Mathf.Exp(-t / .006f) * 2.2f;
                data[i] = sample; peak = Mathf.Max(peak, Mathf.Abs(sample));
            }
            return Clip("Procedural metal hit", data, rate, peak);
        }

        static AudioClip Clip(string name, float[] data, int rate, float peak)
        {
            float gain = peak > 0 ? .9f / peak : 1;
            for (int i = 0; i < data.Length; i++) data[i] *= gain;
            var clip = AudioClip.Create(name, data.Length, 1, rate, false); clip.SetData(data, 0); return clip;
        }
    }
}
