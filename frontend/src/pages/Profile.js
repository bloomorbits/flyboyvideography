import { useEffect, useState } from "react";
import { toast } from "sonner";
import { supabase } from "../lib/supabase";
import { useAuth } from "../context/AuthContext";
import { Btn, Card, Input, Label, PageHeader } from "../components/ui";

export default function Profile() {
  const { profile, loadProfile } = useAuth();
  const [form, setForm] = useState({ full_name: "", company: "", phone: "" });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (profile) setForm({ full_name: profile.full_name || "", company: profile.company || "", phone: profile.phone || "" });
  }, [profile]);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    const { error } = await supabase
      .from("clients")
      .update({ full_name: form.full_name, company: form.company || null, phone: form.phone || null })
      .eq("id", profile.id);
    setBusy(false);
    if (error) return toast.error(error.message);
    toast.success("Profile updated");
    loadProfile();
  };

  if (!profile) return null;

  return (
    <div data-testid="profile-page">
      <PageHeader kicker="Your account" title="Profile" />
      <Card className="max-w-xl p-8">
        <form onSubmit={save} className="space-y-6">
          <div>
            <Label>Email (managed by login)</Label>
            <Input data-testid="profile-email-input" value={profile.email} disabled className="opacity-50" />
          </div>
          <div>
            <Label>Full name</Label>
            <Input data-testid="profile-name-input" value={form.full_name} onChange={set("full_name")} required />
          </div>
          <div>
            <Label>Company</Label>
            <Input data-testid="profile-company-input" value={form.company} onChange={set("company")} placeholder="Acme Media" />
          </div>
          <div>
            <Label>Phone</Label>
            <Input data-testid="profile-phone-input" type="tel" value={form.phone} onChange={set("phone")} placeholder="+44 7700 900000" />
          </div>
          <Btn data-testid="profile-save-btn" type="submit" disabled={busy}>
            {busy ? "Saving…" : "Save changes"}
          </Btn>
        </form>
      </Card>
    </div>
  );
}
