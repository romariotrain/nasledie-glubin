using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace SwordsmanTest
{
    // A wide crescent swept by the actual blade, smoothed between frames and shaded by Swordsman/SlashArc.
    // Three rails: inner body near the hilt, the cutting edge past the tip, and an outer glow halo.
    // Also owns SlashFeedback (impact sparks), so CombatPlayer needs no extra wiring.
    public class SwordRibbon : MonoBehaviour
    {
        public Transform bladeBase, bladeTip;
        public Material material;
        [Tooltip("Catmull-Rom steps between two frame samples")] public int smoothing = 4;
        // Measured in-game on v010: strikes reach 6-9 m/s at the tip, wind-ups and returns to guard stay under ~4.
        [Tooltip("Tip speed (m/s) above which an attack draws the arc")] public float sweepSpeed = 4.5f;
        [Tooltip("Pulls the arc towards a horizontal plane at chest height so it reads from the top camera")]
        [Range(0, 1)] public float flatten = .3f;

        // How big and how long each move's crescent is; the finisher is the loudest on screen.
        struct Profile { public float lifetime, reach, glow, inner, intensity; }
        static Profile ProfileFor(string state)
        {
            switch (state)
            {
                case "attack_1": return new Profile { lifetime = .26f, reach = .55f, glow = .35f, inner = .15f, intensity = 1f };
                case "attack_2": return new Profile { lifetime = .3f, reach = .7f, glow = .45f, inner = .1f, intensity = 1.15f };
                case "attack_3": return new Profile { lifetime = .4f, reach = 1.05f, glow = .7f, inner = .05f, intensity = 1.45f };
                case "piercing_lunge": return new Profile { lifetime = .3f, reach = .8f, glow = .4f, inner = .2f, intensity = 1.2f };
                default: return new Profile { lifetime = .26f, reach = .55f, glow = .35f, inner = .15f, intensity = 1f };
            }
        }

        struct Sample { public Vector3 a, b, c; public float age, lifetime, intensity; public Color colour; }
        readonly List<Sample> samples = new List<Sample>();
        readonly List<Vector3> vertices = new List<Vector3>();
        readonly List<Color> colours = new List<Color>();
        readonly List<Vector3> uv = new List<Vector3>(); // age, rail, intensity
        readonly List<int> triangles = new List<int>();
        static readonly float[] railV = { 0, .78f, 1 };
        GameObject surface; Mesh mesh; CombatPlayer player; SlashFeedback feedback;
        Vector3 lastTip; bool hasLastTip;

        public void Tick(float dt, bool emit, Color colour)
        {
            if (!surface)
            {
                surface = new GameObject("Swept sword ribbon");
                mesh = new Mesh { name = "Transient sword sweep" }; mesh.MarkDynamic();
                surface.AddComponent<MeshFilter>().sharedMesh = mesh;
                var renderer = surface.AddComponent<MeshRenderer>(); renderer.sharedMaterial = material;
                renderer.shadowCastingMode = ShadowCastingMode.Off; renderer.receiveShadows = false;
                player = GetComponent<CombatPlayer>();
                feedback = GetComponent<SlashFeedback>(); if (!feedback) feedback = gameObject.AddComponent<SlashFeedback>();
                feedback.Initialize(player, this);
            }
            feedback.Tick(dt);
            for (int i = samples.Count - 1; i >= 0; i--)
            {
                var s = samples[i]; s.age += dt;
                if (s.age > s.lifetime) samples.RemoveAt(i); else samples[i] = s;
            }
            if (dt > 0 && bladeBase && bladeTip)
            {
                // The hit window leads the visible swing in several clips, so draw while the blade
                // actually travels fast during an attack rather than only inside the hit window.
                Vector3 hilt = bladeBase.position, tip = bladeTip.position;
                float jump = hasLastTip ? Vector3.Distance(tip, lastTip) : 0, speed = jump / dt;
                lastTip = tip; hasLastTip = true;
                if (jump > 1.2f) { samples.Clear(); speed = 0; } // teleport or arena reset, not a swing
                string state = player ? player.State : "";
                bool swinging = player ? state.StartsWith("attack_") || state == "piercing_lunge" : emit;                if (swinging && speed > sweepSpeed)
                {
                    var p = ProfileFor(state);
                    float chest = (player ? player.transform.position.y : hilt.y) + 1f;
                    Vector3 Flat(Vector3 v) => new Vector3(v.x, Mathf.Lerp(v.y, chest, flatten), v.z);
                    Vector3 blade = tip - hilt;
                    Color c = Palette(state, colour);
                    samples.Add(new Sample { a = Flat(hilt + blade * p.inner), b = Flat(tip + blade * p.reach),
                        c = Flat(tip + blade * (p.reach + p.glow)), lifetime = p.lifetime, intensity = p.intensity, colour = c });
                }
            }
            if (samples.Count > 48) samples.RemoveAt(0);
            mesh.Clear(); if (samples.Count < 2) return;

            vertices.Clear(); colours.Clear(); uv.Clear(); triangles.Clear();
            int n = samples.Count, steps = Mathf.Max(1, smoothing);
            for (int i = 0; i < n - 1; i++)
            {
                var p0 = samples[Mathf.Max(i - 1, 0)]; var p1 = samples[i]; var p2 = samples[i + 1]; var p3 = samples[Mathf.Min(i + 2, n - 1)];
                for (int k = 0; k < steps || (i == n - 2 && k == steps); k++)
                {
                    float t = k / (float)steps;
                    float age = Mathf.Lerp(p1.age / p1.lifetime, p2.age / p2.lifetime, t);
                    Color c = Color.Lerp(p1.colour, p2.colour, t); float boost = Mathf.Lerp(p1.intensity, p2.intensity, t);
                    vertices.Add(CatmullRom(p0.a, p1.a, p2.a, p3.a, t));
                    vertices.Add(CatmullRom(p0.b, p1.b, p2.b, p3.b, t));
                    vertices.Add(CatmullRom(p0.c, p1.c, p2.c, p3.c, t));
                    for (int r = 0; r < 3; r++) { uv.Add(new Vector3(age, railV[r], boost)); colours.Add(c); }
                }
            }
            for (int v = 0; v + 5 < vertices.Count; v += 3)
                for (int r = 0; r < 2; r++)
                {
                    int a = v + r, b = v + r + 1, c = v + r + 3, d = v + r + 4;
                    triangles.Add(a); triangles.Add(b); triangles.Add(c);
                    triangles.Add(b); triangles.Add(d); triangles.Add(c);
                }
            mesh.SetVertices(vertices); mesh.SetColors(colours); mesh.SetUVs(0, uv); mesh.SetTriangles(triangles, 0);
            mesh.RecalculateBounds();
        }

        // Light combo is pale steel-gold, the finisher burns crimson like the coat accents, the lunge is cold.
        public static Color Palette(string state, Color fallback)
        {
            switch (state)
            {
                case "attack_1": return new Color(1f, .86f, .58f, .85f);
                case "attack_2": return new Color(1f, .62f, .26f, .9f);
                case "attack_3": return new Color(1f, .2f, .1f, 1f);
                case "piercing_lunge": return new Color(.45f, .9f, 1f, .9f);
                default: return fallback;
            }
        }

        static Vector3 CatmullRom(Vector3 p0, Vector3 p1, Vector3 p2, Vector3 p3, float t)
        {
            float t2 = t * t, t3 = t2 * t;
            return .5f * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (3 * p1 - p0 - 3 * p2 + p3) * t3);
        }

        void OnDestroy() { if (mesh) Destroy(mesh); if (surface) Destroy(surface); }
    }
}
