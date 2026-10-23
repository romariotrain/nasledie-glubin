using System;
using UnityEngine;
using UnityEngine.Animations;
using UnityEngine.Playables;

namespace SwordsmanTest
{
    // A manual clock keeps animation, hit windows and local hitstop in sync.
    public class CombatAnimation : MonoBehaviour
    {
        public Animator animator;
        public AnimationClip[] clips;
        PlayableGraph graph;
        AnimationMixerPlayable mixer;
        AnimationClipPlayable[] nodes;
        float[] weights, previous;
        string current;
        float blendTime, blendDuration;
        public string Current => current;

        public void Initialize()
        {
            if (graph.IsValid()) return;
            animator.applyRootMotion = false;
            animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;
            graph = PlayableGraph.Create("Swordsman combat clock");
            graph.SetTimeUpdateMode(DirectorUpdateMode.Manual);
            mixer = AnimationMixerPlayable.Create(graph, clips.Length);
            nodes = new AnimationClipPlayable[clips.Length];
            weights = new float[clips.Length]; previous = new float[clips.Length];
            for (int i = 0; i < clips.Length; i++)
            {
                nodes[i] = AnimationClipPlayable.Create(graph, clips[i]);
                nodes[i].SetApplyFootIK(false); nodes[i].SetApplyPlayableIK(false);
                nodes[i].SetSpeed(0);
                graph.Connect(nodes[i], 0, mixer, i);
            }
            var output = AnimationPlayableOutput.Create(graph, "Character", animator);
            output.SetSourcePlayable(mixer); graph.Play();
        }

        public void Sample(string name, float time, float delta, float fade = .075f)
        {
            Initialize();
            int index = Array.FindIndex(clips, c => c.name == name);
            if (index < 0) throw new InvalidOperationException("Missing imported clip " + name);
            if (current != name)
            {
                Array.Copy(weights, previous, weights.Length);
                blendTime = current == null ? fade : 0;
                blendDuration = Mathf.Max(.001f, fade); current = name;
            }
            blendTime += delta;
            float blend = Mathf.SmoothStep(0, 1, Mathf.Clamp01(blendTime / blendDuration));
            for (int i = 0; i < clips.Length; i++)
            {
                weights[i] = Mathf.Lerp(previous[i], i == index ? 1 : 0, blend);
                mixer.SetInputWeight(i, weights[i]);
            }
            bool loop = name == "idle" || name == "run";
            nodes[index].SetTime(loop ? Mathf.Repeat(time, clips[index].length) : Mathf.Min(time, clips[index].length));
            graph.Evaluate(0);
        }

        void OnDestroy() { if (graph.IsValid()) graph.Destroy(); }
    }
}
