using System;
using UnityEngine;

namespace SwordsmanTest
{
    [Serializable]
    public class MoveDefinition
    {
        public string id;
        public float duration, activeStart, activeEnd, bufferStart, cancelStart;
        public float damage, reach, arc, knockback, hitstop;
        public float travelDistance, travelStart, travelEnd, invulnerableStart, invulnerableEnd;
    }

    [CreateAssetMenu(menuName = "Swordsman/Combat Tuning")]
    public class CombatTuning : ScriptableObject
    {
        public float runSpeed = 4.3f, acceleration = 22f, turnSpeed = 1100f;
        public float runReferenceSpeed = 3.9f;
        public float dodgeCooldown = .55f, lungeCooldown = 1.1f;
        public bool allowRecoveryDodgeCancel = true;
        public MoveDefinition[] moves;

        public MoveDefinition Get(string id)
        {
            foreach (var move in moves) if (move.id == id) return move;
            throw new ArgumentException("Unknown move: " + id);
        }
    }
}
