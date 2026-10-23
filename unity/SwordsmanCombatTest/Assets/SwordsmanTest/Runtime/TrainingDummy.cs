using UnityEngine;

namespace SwordsmanTest
{
    public class TrainingDummy : MonoBehaviour
    {
        public float maximumHealth = 200;
        public Transform body;
        public Renderer bodyRenderer;
        public Color restingTint = new Color(.64f,.32f,.16f);
        public float Health { get; private set; }
        public int Hits { get; private set; }
        public float LastDamage { get; private set; }
        Vector3 origin, velocity;
        float flash;
        MaterialPropertyBlock block;
        public void Initialize()
        {
            origin = transform.position; Health = maximumHealth;
            block = new MaterialPropertyBlock();
        }
        void Start() { if (block == null) Initialize(); }
        public void ResetDummy()
        {
            transform.position = origin; velocity = Vector3.zero;
            Health = maximumHealth; Hits = 0; LastDamage = 0; flash = 0;
            if (body) body.localRotation = Quaternion.identity;
        }
        public void Hit(float damage, Vector3 direction, float knockback)
        {
            Health = Mathf.Max(0, Health - damage); Hits++; LastDamage = damage;
            velocity += direction.normalized * knockback * 9;
            flash = .12f;
        }
        public void Tick(float dt)
        {
            transform.position += velocity * dt;
            velocity *= Mathf.Exp(-9 * dt);
            flash = Mathf.Max(0, flash - dt);
            if (body) body.localRotation = Quaternion.Slerp(body.localRotation,
                Quaternion.Euler(velocity.z * 2, 0, -velocity.x * 2), 1 - Mathf.Exp(-20 * dt));
            if (bodyRenderer && block != null)
            {
                bodyRenderer.GetPropertyBlock(block);
                block.SetColor("_Color", flash > 0 ? Color.white : restingTint);
                block.SetColor("_EmissionColor",flash>0 ? new Color(.55f,.20f,.04f) : Color.black);
                bodyRenderer.SetPropertyBlock(block);
            }
        }
    }
}
