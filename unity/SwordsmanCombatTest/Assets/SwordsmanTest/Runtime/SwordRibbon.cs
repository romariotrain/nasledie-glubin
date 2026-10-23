using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace SwordsmanTest
{
    // A crescent swept by the actual blade, smoothed between frames and shaded by Swordsman/SlashArc.
    // Also owns SlashFeedback (swing/impact audio and sparks), so CombatPlayer needs no extra wiring.
    public class SwordRibbon : MonoBehaviour
    {
        public Transform bladeBase, bladeTip;
        public Material material;
        [Tooltip("Seconds a swept sample stays visible")] public float lifetime = .24f;
        [Tooltip("Catmull-Rom steps between two frame samples")] public int smoothing = 4;
        [Tooltip("Arc reaches past the tip by this fraction of the blade")] public float tipExtension = .32f;
        [Tooltip("Inner edge of the arc, 0 = hilt, 1 = tip")] public float innerEdge = .25f;
        [Tooltip("Tip speed (m/s) above which an attack draws the arc")] public float sweepSpeed = 3.5f;
        struct Sample { public Vector3 a, b; public float age; }
        readonly List<Sample> samples = new List<Sample>();
        readonly List<Vector3> vertices = new List<Vector3>();
        readonly List<Color> colours = new List<Color>();
        readonly List<Vector2> uv = new List<Vector2>();
        readonly List<int> triangles = new List<int>();
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
                if (s.age > lifetime) samples.RemoveAt(i); else samples[i] = s;
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
                bool swinging = player ? state.StartsWith("attack_") || state == "piercing_lunge" : emit;
                if (swinging && speed > sweepSpeed)
                    samples.Add(new Sample { a = Vector3.Lerp(hilt, tip, innerEdge), b = tip + (tip - hilt) * tipExtension });
            }
            if (samples.Count > 40) samples.RemoveAt(0);
            mesh.Clear(); if (samples.Count < 2) return;

            colour = Palette(player ? player.State : "", colour);
            vertices.Clear(); colours.Clear(); uv.Clear(); triangles.Clear();
            int n = samples.Count, steps = Mathf.Max(1, smoothing);
            for (int i = 0; i < n - 1; i++)
            {
                var p0 = samples[Mathf.Max(i - 1, 0)]; var p1 = samples[i]; var p2 = samples[i + 1]; var p3 = samples[Mathf.Min(i + 2, n - 1)];
                for (int k = 0; k < steps || (i == n - 2 && k == steps); k++)
                {
                    float t = k / (float)steps;
                    float age = Mathf.Lerp(p1.age, p2.age, t) / lifetime;
                    vertices.Add(CatmullRom(p0.a, p1.a, p2.a, p3.a, t)); uv.Add(new Vector2(age, 0)); colours.Add(colour);
                    vertices.Add(CatmullRom(p0.b, p1.b, p2.b, p3.b, t)); uv.Add(new Vector2(age, 1)); colours.Add(colour);
                }
            }
            for (int v = 0; v + 3 < vertices.Count; v += 2)
            {
                triangles.Add(v); triangles.Add(v + 1); triangles.Add(v + 2);
                triangles.Add(v + 1); triangles.Add(v + 3); triangles.Add(v + 2);
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
                case "attack_2": return new Color(1f, .68f, .32f, .9f);
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
